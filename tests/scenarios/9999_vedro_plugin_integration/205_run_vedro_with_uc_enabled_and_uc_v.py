from contexts.compose_file import compose_file
from contexts.isolated_project import isolated_project
from contexts.no_docker_containers import no_docker_containers
from contexts.vedro_subprocess_project import vedro_subprocess_project
from interfaces.vedro_cli import CliRunner
import vedro


class Scenario(vedro.Scenario):
    subject = 'run vedro with uc enabled and --uc-v'

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

    async def given_vedro_project_with_plugin_configured(self):
        self.project_dir = vedro_subprocess_project(
            vedro_cfg=f"""
import vedro

from uber_compose import ComposeConfig
from uber_compose import DEFAULT_COMPOSE
from uber_compose import DEFAULT_ENV_DESCRIPTION
from uber_compose import Environment
from uber_compose import Service
from uber_compose import VedroUberCompose


class Config(vedro.Config):
    class Plugins(vedro.Config.Plugins):
        class UberCompose(VedroUberCompose):
            enabled = True
            default_env = Environment(Service("s1"), description=DEFAULT_ENV_DESCRIPTION)
            compose_cfgs = {{
                DEFAULT_COMPOSE: ComposeConfig(compose_files="{self.compose_filename}"),
            }}
""",
            scenarios={
                'test_env_is_up.py': """
import vedro


class Scenario(vedro.Scenario):
    subject = 'scenario runs with verbose logging'

    def when_nothing_special_happens(self):
        self.result = 'ok'

    def then_it_should_just_pass(self):
        assert self.result == 'ok'
"""
            },
        )

    async def when_vedro_is_run_with_known_verbosity_preset(self):
        self.known_run = await CliRunner().run_vedro(
            self.project_dir, args=['run', 'scenarios/', '--uc-v', 'VERBOSE']
        )

    async def then_it_should_exit_with_code_zero(self):
        assert self.known_run.returncode == 0, self.known_run.stdout + self.known_run.stderr

    async def when_vedro_is_run_with_unknown_verbosity_preset(self):
        self.unknown_run = await CliRunner().run_vedro(
            self.project_dir, args=['run', 'scenarios/', '--uc-v', 'NOPE']
        )

    async def then_it_should_reject_unknown_preset(self):
        assert self.unknown_run.returncode != 0
        assert 'invalid choice' in self.unknown_run.stderr.lower()
