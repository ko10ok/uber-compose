import json

from contexts.compose_file import compose_file
from contexts.isolated_project import isolated_project
from contexts.no_docker_containers import no_docker_containers
from contexts.no_docker_containers import retrieve_all_docker_containers
from contexts.vedro_subprocess_project import vedro_subprocess_project
from helpers.env_vars import patch_env
from interfaces.vedro_cli import CliRunner
import vedro
import vedro.plugins.temp_keeper as temp_keeper

from uber_compose.helpers.labels import Label

SCENARIO_TEMPLATE = """
import json
import os

import vedro

from uber_compose import Environment
from uber_compose import Service


class Scenario(vedro.Scenario):
    subject = 'scenario {name}'
    env = Environment(Service('s1'), description='env-a')

    def when_worker_identity_is_recorded(self):
        observations_dir = os.environ['UC_TEST_OBSERVATIONS_DIR']
        with open(os.path.join(observations_dir, '{name}.json'), 'w') as file:
            json.dump({{
                'worker_id': os.environ.get('UC_WORKER_ID'),
                'pid': os.getpid(),
            }}, file)
"""


class Scenario(vedro.Scenario):
    subject = 'run vedro with workers per env greater than scenarios count'

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
        self.observations_dir = temp_keeper.create_tmp_dir(prefix='uc-more-workers-than-scenarios-')
        patch_env({'UC_TEST_OBSERVATIONS_DIR': str(self.observations_dir)})

    async def given_vedro_project_with_two_scenarios(self):
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
                    workers_per_env={{"env-a": 1}},
                ),
            }}

        class UberComposeParallel(VedroUberComposeParallel):
            enabled = True
""",
            scenarios={
                f'test_env_a_{index}.py': SCENARIO_TEMPLATE.format(name=f'env_a_{index}')
                for index in range(2)
            },
        )

    async def when_vedro_is_run_with_three_workers(self):
        self.run_result = await CliRunner().run_vedro(
            self.project_dir,
            args=['run', 'scenarios/', '--uc-mt', '--uc-wpe', '3'],
        )

    async def then_it_should_exit_with_code_zero(self):
        assert self.run_result.returncode == 0, self.run_result.stdout + self.run_result.stderr

    async def and_it_should_run_each_scenario_once(self):
        self.observations = {
            file.stem: json.loads(file.read_text())
            for file in self.observations_dir.glob('*.json')
        }
        assert set(self.observations) == {'env_a_0', 'env_a_1'}

    async def and_it_should_use_only_two_workers(self):
        worker_ids = {observation['worker_id'] for observation in self.observations.values()}
        pids = {observation['pid'] for observation in self.observations.values()}
        assert None not in worker_ids
        assert len(worker_ids) == 2
        assert len(pids) == 2

    async def and_it_should_start_only_two_replicas(self):
        containers = retrieve_all_docker_containers()
        assert len(containers) == 2
        env_ids = {
            container.get('Labels', {}).get(Label.ENV_ID)
            for container in containers
        }
        assert len(env_ids) == 2
