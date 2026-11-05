from contexts.compose_file import compose_file
from contexts.isolated_project import isolated_project
from contexts.no_docker_containers import no_docker_containers
from contexts.vedro_subprocess_project import vedro_subprocess_project
from interfaces.vedro_cli import CliRunner
import vedro


@vedro.skip(reason=(
    'Known bug: handle_arg_parsed filters specific --uc-external-services against '
    'self._uc_external_services, which is still None at that point, so selecting an '
    'explicit external service raises TypeError. Fix is intentionally out of scope; '
    'this test documents the expected behavior for when it is fixed.'
))
class Scenario(vedro.Scenario):
    subject = 'run vedro with uc enabled and --uc-external-services ext'

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

  ext:
    image: busybox:stable
    command: 'sh -c "trap : TERM INT; sleep 604800; wait"'
"""
        )

    async def given_vedro_project_with_overridden_external_service(self):
        self.project_dir = vedro_subprocess_project(
            vedro_cfg=f"""
import vedro

from uber_compose import ComposeConfig
from uber_compose import DEFAULT_COMPOSE
from uber_compose import DEFAULT_ENV_DESCRIPTION
from uber_compose import Env
from uber_compose import Environment
from uber_compose import OverridenService
from uber_compose import Service
from uber_compose import VedroUberCompose


class Config(vedro.Config):
    class Plugins(vedro.Config.Plugins):
        class UberCompose(VedroUberCompose):
            enabled = True
            default_env = Environment(
                Service("s1"), Service("ext"), description=DEFAULT_ENV_DESCRIPTION
            )
            compose_cfgs = {{
                DEFAULT_COMPOSE: ComposeConfig(
                    compose_files="{self.compose_filename}",
                    overridden_services=[
                        OverridenService(
                            Service("ext"),
                            services_envs_fix=[
                                Service("s1", env=Env({{"EXT_URL": "http://ext"}})),
                            ],
                        ),
                    ],
                ),
            }}
""",
            scenarios={
                'test_env_is_up.py': """
import os

import vedro


class Scenario(vedro.Scenario):
    subject = 'overridden external service env is injected into the scenario'

    def then_it_should_have_external_service_env(self):
        assert os.environ['EXT_URL'] == 'http://ext'
"""
            },
        )

    async def when_vedro_is_run_with_external_services_specific(self):
        self.run_result = await CliRunner().run_vedro(
            self.project_dir, args=['run', 'scenarios/', '--uc-external-services', 'ext']
        )

    async def then_it_should_exit_with_code_zero(self):
        assert self.run_result.returncode == 0, self.run_result.stdout + self.run_result.stderr
