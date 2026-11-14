import json

from contexts.compose_file import compose_file
from contexts.isolated_project import isolated_project
from contexts.no_docker_containers import no_docker_containers
from contexts.vedro_subprocess_project import vedro_subprocess_project
from helpers.env_vars import patch_env
from interfaces.vedro_cli import CliRunner
import vedro
import vedro.plugins.temp_keeper as temp_keeper

SCENARIO_TEMPLATE = """
import json
import os

import vedro

from uber_compose import Environment
from uber_compose import Service


class Scenario(vedro.Scenario):
    subject = '{subject}'
    env = Environment(Service('s1'), description='{env_description}')

    def when_worker_identity_is_recorded(self):
        observations_dir = os.environ['UC_TEST_OBSERVATIONS_DIR']
        with open(os.path.join(observations_dir, '{name}.json'), 'w') as file:
            json.dump({{
                'worker_id': os.environ.get('UC_WORKER_ID'),
                'pid': os.getpid(),
            }}, file)
"""


class Scenario(vedro.Scenario):
    subject = 'run vedro with uc mt and default workers per env'

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
        self.observations_dir = temp_keeper.create_tmp_dir(prefix='uc-default-workers-')
        patch_env({'UC_TEST_OBSERVATIONS_DIR': str(self.observations_dir)})

    async def given_vedro_project_with_two_envs(self):
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
            scenarios={
                'test_env_a.py': SCENARIO_TEMPLATE.format(
                    subject='env-a scenario',
                    env_description='env-a',
                    name='env_a',
                ),
                'test_env_b.py': SCENARIO_TEMPLATE.format(
                    subject='env-b scenario',
                    env_description='env-b',
                    name='env_b',
                ),
            },
        )

    async def when_vedro_is_run_with_uc_mt(self):
        self.run_result = await CliRunner().run_vedro(
            self.project_dir, args=['run', 'scenarios/', '--uc-mt']
        )

    async def then_it_should_exit_with_code_zero(self):
        assert self.run_result.returncode == 0, self.run_result.stdout + self.run_result.stderr

    async def and_it_should_run_each_env_in_its_own_worker(self):
        observations = {
            file.stem: json.loads(file.read_text())
            for file in self.observations_dir.glob('*.json')
        }
        assert set(observations) == {'env_a', 'env_b'}
        worker_ids = {observation['worker_id'] for observation in observations.values()}
        assert None not in worker_ids
        assert len(worker_ids) == 2
        assert observations['env_a']['pid'] != observations['env_b']['pid']
