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
    subject = 'run vedro with uc and parallel plugins enabled and uc_parallel 2 with one env group'

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
        self.observations_dir = temp_keeper.create_tmp_dir(prefix='uc-parallel-observations-')
        patch_env({'UC_TEST_OBSERVATIONS_DIR': str(self.observations_dir)})

    async def given_vedro_project_with_both_plugins_and_one_env_group(self):
        scenario_template = """
import json
import os

import vedro

from uber_compose import Environment
from uber_compose import Service


class Scenario(vedro.Scenario):
    subject = 'scenario {name} for env-a'
    env = Environment(Service('s1'), description='env-a')

    def when_worker_identity_is_recorded(self):
        observations_dir = os.environ['UC_TEST_OBSERVATIONS_DIR']
        with open(os.path.join(observations_dir, '{name}.json'), 'w') as file:
            json.dump({{
                'worker_id': os.environ.get('UC_WORKER_ID'),
                'pid': os.getpid(),
            }}, file)
"""
        scenarios = {
            f'test_{name}.py': scenario_template.format(name=name)
            for name in ('env_a_1', 'env_a_2', 'env_a_3')
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
                DEFAULT_COMPOSE: ComposeConfig(compose_files="{self.compose_filename}"),
            }}

        class UberComposeParallel(VedroUberComposeParallel):
            enabled = True
""",
            scenarios=scenarios,
        )

    async def when_vedro_is_run_with_uc_parallel_two(self):
        self.run_result = await CliRunner().run_vedro(
            self.project_dir, args=['run', 'scenarios/', '--uc-parallel', '2']
        )

    async def then_it_should_exit_with_code_zero(self):
        assert self.run_result.returncode == 0, self.run_result.stdout + self.run_result.stderr

    async def and_it_should_keep_the_env_group_in_a_single_worker(self):
        observations = {
            file.stem: json.loads(file.read_text())
            for file in self.observations_dir.glob('*.json')
        }
        assert set(observations) == {'env_a_1', 'env_a_2', 'env_a_3'}
        worker_ids = {observation['worker_id'] for observation in observations.values()}
        assert len(worker_ids) == 1
        assert None not in worker_ids

    async def and_it_should_run_the_env_group_in_a_single_process(self):
        observations = {
            file.stem: json.loads(file.read_text())
            for file in self.observations_dir.glob('*.json')
        }
        pids = {observation['pid'] for observation in observations.values()}
        assert len(pids) == 1

    async def and_it_should_start_only_one_container_for_the_env_group(self):
        containers = retrieve_all_docker_containers()
        assert len(containers) == 1
        assert containers[0].get('Labels', {}).get(Label.TEMPLATE_SERVICE_NAME) == 's1'
