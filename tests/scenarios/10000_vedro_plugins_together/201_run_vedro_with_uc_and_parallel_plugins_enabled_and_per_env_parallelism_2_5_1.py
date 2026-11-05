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


class Scenario(vedro.Scenario):
    subject = 'run vedro with uc and parallel plugins enabled and per env parallelism 2 5 1'

    async def given_no_docker_containers(self):
        no_docker_containers()

    async def given_env_replica_counts(self):
        self.replicas = {'env-a': 2, 'env-b': 5, 'env-c': 1}

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
        self.observations_dir = temp_keeper.create_tmp_dir(prefix='uc-parallel-observations-')
        patch_env({'UC_TEST_OBSERVATIONS_DIR': str(self.observations_dir)})

    async def given_vedro_project_with_per_env_parallelism(self):
        scenarios = {}
        for env_description, replicas in self.replicas.items():
            for index in range(replicas):
                name = f"{env_description.replace('-', '_')}_{index}"
                scenarios[f'test_{name}.py'] = self._scenario_source(env_description, name)

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
                    env_parallelism={self.replicas},
                ),
            }}

        class UberComposeParallel(VedroUberComposeParallel):
            enabled = True
""",
            scenarios=scenarios,
        )

    async def when_vedro_is_run_with_per_env_parallelism(self):
        self.run_result = await CliRunner().run_vedro(self.project_dir, args=['run', 'scenarios/'])

    async def then_it_should_exit_with_code_zero(self):
        assert self.run_result.returncode == 0, self.run_result.stdout + self.run_result.stderr

    async def and_it_should_start_configured_number_of_replicas_per_env(self):
        containers = retrieve_all_docker_containers()
        replicas_by_env = {}
        for container in containers:
            env_description = container.get('Labels', {}).get(Label.ENV_DESCRIPTION)
            replicas_by_env[env_description] = replicas_by_env.get(env_description, 0) + 1
        assert replicas_by_env == self.replicas

    async def and_it_should_run_each_env_group_in_configured_number_of_workers(self):
        observations = self._read_observations()
        assert len(observations) == sum(self.replicas.values())
        workers_by_env = {}
        for observation in observations.values():
            env_description = observation['env']
            workers_by_env.setdefault(env_description, set()).add(observation['worker_id'])
        for env_description, replicas in self.replicas.items():
            assert len(workers_by_env[env_description]) == replicas
            assert None not in workers_by_env[env_description]

    def _read_observations(self):
        observations = {}
        for file in self.observations_dir.glob('*.json'):
            observations[file.stem] = json.loads(file.read_text())
        return observations

    @staticmethod
    def _scenario_source(env_description: str, name: str) -> str:
        return f"""
import json
import os

import vedro

from uber_compose import Environment
from uber_compose import Service


class Scenario(vedro.Scenario):
    subject = 'scenario {name}'
    env = Environment(Service('s1'), description='{env_description}')

    def then_it_should_record_worker_identity(self):
        observations_dir = os.environ['UC_TEST_OBSERVATIONS_DIR']
        with open(os.path.join(observations_dir, '{name}.json'), 'w') as file:
            json.dump({{
                'env': '{env_description}',
                'worker_id': os.environ.get('UC_WORKER_ID'),
                'pid': os.getpid(),
            }}, file)
"""
