import json

from contexts.compose_file import compose_file
from contexts.isolated_project import isolated_project
from contexts.no_docker_containers import no_docker_containers
from contexts.vedro_subprocess_project import vedro_subprocess_project
from helpers.env_vars import patch_env
from interfaces.vedro_cli import CliRunner
import vedro
import vedro.plugins.temp_keeper as temp_keeper


class Scenario(vedro.Scenario):
    subject = 'run vedro with uc and parallel plugins enabled and the uber compose current env api'

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
        self.observations_dir = temp_keeper.create_tmp_dir(prefix='uc-current-env-observations-')
        patch_env({'UC_TEST_OBSERVATIONS_DIR': str(self.observations_dir)})

    async def given_vedro_project_with_two_replicas(self):
        scenario_template = """
import json
import os

import vedro

from uber_compose import Env
from uber_compose import Environment
from uber_compose import Service
from uber_compose import TheUberCompose


class Scenario(vedro.Scenario):
    subject = 'scenario {name} reports current env api'
    env = Environment(
        Service('s1', env=Env({{'PARAM': 'value'}})),
        description='env-a',
    )

    def when_current_env_api_is_recorded(self):
        client = TheUberCompose()
        observations_dir = os.environ['UC_TEST_OBSERVATIONS_DIR']
        with open(os.path.join(observations_dir, '{name}.json'), 'w') as file:
            json.dump({{
                'env_id': client.current_env_id(),
                'current_env_id': client.current_env_id(),
                'worker_id': client.current_worker_id(),
                'workers_total': client.current_workers_total(),
                'replica_index': client.current_replica_index(),
                'replicas_total': client.current_replicas_total(),
                'namespace': client.current_namespace(),
                'run_depth': client.current_run_depth(),
                'is_child_project': client.is_child_project(),
                'service_env': client.current_service_env('s1'),
            }}, file)
"""
        scenarios = {
            f'test_{name}.py': scenario_template.format(name=name)
            for name in ('env_a_1', 'env_a_2')
        }

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
                    workers_per_env={{"env-a": 2}},
                ),
            }}

        class UberComposeParallel(VedroUberComposeParallel):
            enabled = True
""",
            scenarios=scenarios,
        )

    async def when_vedro_is_run(self):
        self.run_result = await CliRunner().run_vedro(self.project_dir, args=['run', 'scenarios/', '--uc-mt'])

    async def then_it_should_exit_with_code_zero(self):
        assert self.run_result.returncode == 0, self.run_result.stdout + self.run_result.stderr

    async def and_it_should_expose_current_env_and_worker_parameters(self):
        observations = {
            file.stem: json.loads(file.read_text())
            for file in self.observations_dir.glob('*.json')
        }
        assert len(observations) == 2
        for observation in observations.values():
            replica_index = observation['replica_index']
            replicas_total = observation['replicas_total']
            assert replicas_total == 2
            assert replica_index in (0, 1)
            assert observation['env_id'].startswith(f'w{replica_index}-')
            assert observation['namespace'] == observation['env_id']
            assert observation['workers_total'] == 2
            assert observation['worker_id'] in (0, 1)
            assert observation['run_depth'] == 1
            assert observation['is_child_project'] is True
            assert observation['service_env'] == {'PARAM': 'value'}

    async def and_it_should_pass_the_same_env_id_to_both_api_sources(self):
        observations = {
            file.stem: json.loads(file.read_text())
            for file in self.observations_dir.glob('*.json')
        }
        assert {observation['current_env_id'] for observation in observations.values()} == {
            observation['env_id'] for observation in observations.values()
        }
