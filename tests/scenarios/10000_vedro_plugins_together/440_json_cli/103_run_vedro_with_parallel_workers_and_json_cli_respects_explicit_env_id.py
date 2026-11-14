import json

from contexts.compose_file import compose_file
from contexts.isolated_project import isolated_project
from contexts.no_docker_containers import no_docker_containers
from contexts.vedro_subprocess_project import vedro_subprocess_project
from d42 import schema
from helpers.env_vars import patch_env
from interfaces.vedro_cli import CliRunner
import vedro
import vedro.plugins.temp_keeper as temp_keeper

EXEC_COMMAND = """echo '{"level": "stdout", "MARKER": "'"$MARKER"'"}'"""

SCENARIO_TEMPLATE = """
import json
import os

import vedro

from uber_compose import CommonJsonCli
from uber_compose import Env
from uber_compose import Environment
from uber_compose import Service
from uber_compose import TheUberCompose
from uber_compose.helpers.env_id import get_stable_env_id


ENVS = {
    'env-a': Environment(
        Service('s1', env=Env({'MARKER': 'a'})),
        description='env-a',
    ),
    'env-b': Environment(
        Service('s1', env=Env({'MARKER': 'b'})),
        description='env-b',
    ),
}


class Scenario(vedro.Scenario):
    subject = 'json cli explicit env id in __NAME__'
    env = ENVS['__ENV_DESCRIPTION__']

    async def when_command_is_executed_with_explicit_env_id(self):
        target_env_id = get_stable_env_id(ENVS['env-b'], 0)
        result = await CommonJsonCli(cli_client=TheUberCompose()).exec(
            container='s1',
            command=__COMMAND__,
            env_id=target_env_id,
        )
        observations_dir = os.environ['UC_TEST_OBSERVATIONS_DIR']
        with open(os.path.join(observations_dir, '__NAME__.json'), 'w') as file:
            json.dump({
                'stdout': result.stdout,
                'target_env_id': target_env_id,
                'current_env_id': TheUberCompose().current_env_id(),
            }, file)
"""


class Scenario(vedro.Scenario):
    subject = 'run vedro with parallel workers and json cli respects explicit env id'

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
        self.observations_dir = temp_keeper.create_tmp_dir(prefix='uc-json-cli-explicit-')
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
                DEFAULT_COMPOSE: ComposeConfig(
                    compose_files="{self.compose_filename}",
                    workers_per_env={{"env-a": 1, "env-b": 1}},
                ),
            }}

        class UberComposeParallel(VedroUberComposeParallel):
            enabled = True
""",
            scenarios={
                'test_env_a.py': SCENARIO_TEMPLATE
                .replace('__NAME__', 'env_a')
                .replace('__ENV_DESCRIPTION__', 'env-a')
                .replace('__COMMAND__', repr(EXEC_COMMAND)),
                'test_env_b.py': SCENARIO_TEMPLATE
                .replace('__NAME__', 'env_b')
                .replace('__ENV_DESCRIPTION__', 'env-b')
                .replace('__COMMAND__', repr(EXEC_COMMAND)),
            },
        )

    async def when_vedro_is_run_with_uc_mt(self):
        self.run_result = await CliRunner().run_vedro(
            self.project_dir, args=['run', 'scenarios/', '--uc-mt']
        )

    async def then_it_should_exit_with_code_zero(self):
        assert self.run_result.returncode == 0, self.run_result.stdout + self.run_result.stderr

    async def and_explicit_env_id_should_override_current_env(self):
        observations = {
            file.stem: json.loads(file.read_text())
            for file in self.observations_dir.glob('*.json')
        }
        assert set(observations) == {'env_a', 'env_b'}
        assert observations['env_a']['target_env_id'] == observations['env_b']['target_env_id']
        assert observations['env_a']['current_env_id'] != observations['env_a']['target_env_id']
        assert observations['env_b']['current_env_id'] == observations['env_b']['target_env_id']
        for observation in observations.values():
            assert observation['stdout'] == schema.list([
                schema.str(json.dumps({'level': 'stdout', 'MARKER': 'b'})),
            ])
