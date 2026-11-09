import json

from contexts.compose_file import compose_file
from contexts.isolated_project import isolated_project
from contexts.no_docker_containers import no_docker_containers
from contexts.no_docker_containers import retrieve_all_docker_containers
from contexts.vedro_subprocess_project import vedro_subprocess_project
from d42 import schema
from helpers.env_vars import patch_env
from interfaces.vedro_cli import CliRunner
from schemas.docker import ContainerSchema
import vedro
import vedro.plugins.temp_keeper as temp_keeper

from uber_compose import Environment
from uber_compose import Service
from uber_compose.core.utils.compose_instance_cfg import get_stable_env_id
from uber_compose.helpers.labels import Label

SCENARIO_TEMPLATE = """
import json
import os

import vedro

from uber_compose import Environment
from uber_compose import Service


class Scenario(vedro.Scenario):
    subject = 'scenario {name}'
    env = Environment(Service('s1'), description='{env_description}')

    def when_worker_identity_is_recorded(self):
        observations_dir = os.environ['UC_TEST_OBSERVATIONS_DIR']
        with open(os.path.join(observations_dir, '{name}.json'), 'w') as file:
            json.dump({{
                'env_description': '{env_description}',
                'worker_id': os.environ.get('UC_WORKER_ID'),
                'pid': os.getpid(),
            }}, file)
"""


class Scenario(vedro.Scenario):
    subject = 'run vedro with uc and parallel with uc env env-a filter'

    async def given_no_docker_containers(self):
        no_docker_containers()

    async def given_isolated_project(self):
        self.project = isolated_project()
        self.compose_filename = 'docker-compose.yaml'
        compose_file(
            self.compose_filename,
            content="""
version: "3"

services:
  s1:
    image: busybox:stable
    command: 'sh -c "trap : TERM INT; sleep 604800; wait"'
"""
        )

    async def given_observations_directory(self):
        self.observations_dir = temp_keeper.create_tmp_dir(prefix='uc-env-env-a-filter-')
        patch_env({'UC_TEST_OBSERVATIONS_DIR': str(self.observations_dir)})

    async def given_vedro_project_with_default_and_other_env_scenarios(self):
        self.env_a_0_id = get_stable_env_id(Environment(Service('s1'), description='env-a'), 0)
        self.env_a_1_id = get_stable_env_id(Environment(Service('s1'), description='env-a'), 1)
        self.env_b_0_id = get_stable_env_id(Environment(Service('s1'), description='env-b'), 0)
        self.env_b_1_id = get_stable_env_id(Environment(Service('s1'), description='env-b'), 1)
        self.project_dir = vedro_subprocess_project(
            vedro_cfg=f"""
import vedro

from uber_compose import ComposeConfig
from uber_compose import DEFAULT_COMPOSE
from uber_compose import VedroUberCompose
from uber_compose import VedroUberComposeParallel


class Config(vedro.Config):
    class Plugins(vedro.Config.Plugins):
        class UberCompose(VedroUberCompose):
            enabled = True
            compose_cfgs = {{
                DEFAULT_COMPOSE: ComposeConfig(
                    compose_files="{self.compose_filename}",
                    workers_per_env={{"env-a": 2, "env-b": 2}},
                ),
            }}

        class UberComposeParallel(VedroUberComposeParallel):
            enabled = True
""",
            scenarios={
                f'test_env_a_{index}.py': SCENARIO_TEMPLATE.format(
                    name=f'env_a_{index}',
                    env_description='env-a',
                )
                for index in range(2)
            } | {
                f'test_env_b_{index}.py': SCENARIO_TEMPLATE.format(
                    name=f'env_b_{index}',
                    env_description='env-b',
                )
                for index in range(2)
            },
        )

    async def when_vedro_is_run_with_parallel_and_env_a_filter(self):
        self.run_result = await CliRunner().run_vedro(
            self.project_dir,
            args=['run', 'scenarios/', '--uc-mt', '--uc-env', 'env-a'],
        )

    async def then_it_should_exit_with_code_zero(self):
        assert self.run_result.returncode == 0, self.run_result.stdout + self.run_result.stderr

    async def and_it_should_run_only_env_a_scenarios(self):
        self.observations = {
            file.stem: json.loads(file.read_text())
            for file in self.observations_dir.glob('*.json')
        }
        assert set(self.observations) == {'env_a_0', 'env_a_1'}
        assert {
            observation['env_description']
            for observation in self.observations.values()
        } == {'env-a'}

    async def and_it_should_start_only_env_a_replicas(self):
        containers = retrieve_all_docker_containers()
        assert containers == schema.list.len(2)
        assert containers == schema.list([
            ...,
            ContainerSchema % {
                'State': 'running',
                'Labels': {
                    'com.docker.compose.service': f's1-{self.env_a_0_id}',
                    Label.ENV_ID: self.env_a_0_id,
                    Label.ENV_DESCRIPTION: 'env-a',
                },
            },
            ...,
        ])
        assert containers == schema.list([
            ...,
            ContainerSchema % {
                'State': 'running',
                'Labels': {
                    'com.docker.compose.service': f's1-{self.env_a_1_id}',
                    Label.ENV_ID: self.env_a_1_id,
                    Label.ENV_DESCRIPTION: 'env-a',
                },
            },
            ...,
        ])
