from contexts.compose_file import compose_file
from contexts.isolated_project import isolated_project
from contexts.no_docker_containers import no_docker_containers
from contexts.vedro_subprocess_project import vedro_subprocess_project
from interfaces.vedro_cli import CliRunner
import vedro


class Scenario(vedro.Scenario):
    subject = 'run vedro with uc enabled and env template variables'

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

    async def given_vedro_project_with_env_template_variables(self):
        self.project_dir = vedro_subprocess_project(
            vedro_cfg=f"""
import vedro

from uber_compose import ComposeConfig
from uber_compose import DEFAULT_COMPOSE
from uber_compose import DEFAULT_ENV_DESCRIPTION
from uber_compose import Env
from uber_compose import Environment
from uber_compose import Service
from uber_compose import VedroUberCompose


class Config(vedro.Config):
    class Plugins(vedro.Config.Plugins):
        class UberCompose(VedroUberCompose):
            enabled = True
            default_env = Environment(
                Service("s1", env=Env({{"FOO": "bar", "TOKEN": "[[test_run_id]]"}})),
                description=DEFAULT_ENV_DESCRIPTION,
            )
            compose_cfgs = {{
                DEFAULT_COMPOSE: ComposeConfig(compose_files="{self.compose_filename}"),
            }}
""",
            scenarios={
                'test_env_is_up.py': """
import os

import vedro

from uber_compose.helpers.current_env import get_current_env_id


class Scenario(vedro.Scenario):
    subject = 'scenario receives env template variables and current env id'

    def then_it_should_have_env_template_variables(self):
        assert os.environ['FOO'] == 'bar'

    def then_it_should_interpolate_test_run_id(self):
        assert os.environ['TOKEN']
        assert os.environ['TOKEN'] != '[[test_run_id]]'

    def then_it_should_point_to_the_current_env(self):
        assert get_current_env_id() == 'default_env_id'
"""
            },
        )

    async def when_vedro_is_run(self):
        self.run_result = await CliRunner().run_vedro(self.project_dir, args=['run', 'scenarios/'])

    async def then_it_should_exit_with_code_zero(self):
        assert self.run_result.returncode == 0, self.run_result.stdout + self.run_result.stderr
