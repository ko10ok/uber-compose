from contexts.compose_file import compose_file
from contexts.isolated_project import isolated_project
from contexts.no_docker_containers import no_docker_containers
from contexts.no_docker_containers import retrieve_all_docker_containers
from contexts.vedro_subprocess_project import vedro_subprocess_project
from d42 import schema
from interfaces.vedro_cli import CliRunner
from schemas.docker import ContainerSchema
import vedro

from uber_compose import DEFAULT_ENV_DESCRIPTION
from uber_compose.helpers.labels import Label


class Scenario(vedro.Scenario):
    subject = 'run vedro with uc mt and default env starts only default env services'

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

  mirror:
    image: busybox:stable
    command: 'sh -c "trap : TERM INT; sleep 604800; wait"'
"""
        )

    async def given_scenarios(self):
        scenario_template = """
import vedro


class Scenario(vedro.Scenario):
    subject = '{subject}'

    def when_nothing_special_happens(self):
        self.result = 'ok'

    def then_it_should_just_pass(self):
        assert self.result == 'ok'
"""
        self.scenarios = {
            'test_scenario_1.py': scenario_template.format(subject='first default env scenario'),
            'test_scenario_2.py': scenario_template.format(subject='second default env scenario'),
        }

    async def given_vedro_project_with_default_env(self):
        self.project_dir = vedro_subprocess_project(
            vedro_cfg=f"""
import vedro

from uber_compose import ComposeConfig
from uber_compose import DEFAULT_COMPOSE
from uber_compose import DEFAULT_ENV_DESCRIPTION
from uber_compose import Environment
from uber_compose import Service
from uber_compose import VedroUberCompose
from uber_compose import VedroUberComposeParallel


class Config(vedro.Config):
    class Plugins(vedro.Config.Plugins):
        class UberCompose(VedroUberCompose):
            enabled = True
            default_env = Environment(Service("s1"), description=DEFAULT_ENV_DESCRIPTION)
            compose_cfgs = {{
                DEFAULT_COMPOSE: ComposeConfig(compose_files="{self.compose_filename}"),
            }}

        class UberComposeParallel(VedroUberComposeParallel):
            enabled = True
""",
            scenarios=self.scenarios,
        )

    async def when_vedro_is_run_with_uc_mt_and_two_workers(self):
        self.run_result = await CliRunner().run_vedro(
            self.project_dir,
            args=['run', 'scenarios/', '--uc-mt', '--uc-wpe=2'],
        )

    async def then_it_should_exit_with_code_zero(self):
        assert self.run_result.returncode == 0, self.run_result.stdout + self.run_result.stderr

    async def and_it_should_start_only_default_env_services(self):
        assert retrieve_all_docker_containers() == schema.list([
            ContainerSchema % {
                'Labels': {
                    Label.ENV_DESCRIPTION: DEFAULT_ENV_DESCRIPTION,
                    Label.TEMPLATE_SERVICE_NAME: 's1',
                },
            },
            ContainerSchema % {
                'Labels': {
                    Label.ENV_DESCRIPTION: DEFAULT_ENV_DESCRIPTION,
                    Label.TEMPLATE_SERVICE_NAME: 's1',
                },
            },
        ])
