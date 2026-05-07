from argparse import Namespace
from unittest.mock import Mock

import vedro

from uber_compose.output.console import LogPolicy
from uber_compose import UpHealthPolicy
from uber_compose.uber_compose import UberCompose
from vedro import catched
from vedro.core import MonotonicScenarioScheduler
from vedro.events import ArgParsedEvent
from vedro.events import StartupEvent

from contexts.compose_file import compose_file
from contexts.no_docker_compose_files import no_docker_compose_files
from contexts.no_docker_containers import no_docker_containers
from helpers.vedro.scenario import make_scenario
from uber_compose import ComposeConfig
from uber_compose import DEFAULT_COMPOSE
from uber_compose import VedroUberCompose
from uber_compose.env_description.env_types import DEFAULT_ENV_DESCRIPTION
from uber_compose.env_description.env_types import Environment
from uber_compose.env_description.env_types import Service
from uber_compose.vedro_plugin.plugin import VedroUberComposePlugin


class Scenario(vedro.Scenario):
    subject = 'handle env-up failure: log error and exit with code 75'

    async def no_docker_containers(self):
        no_docker_containers()

    async def no_docker_copose_files(self):
        no_docker_compose_files()

    async def given_broken_compose_file(self):
        # image that cannot be pulled -> docker compose up will fail
        self.compose_filename_1 = 'docker-compose.yaml'
        compose_file(
            self.compose_filename_1,
            content="""
version: "3"

services:
  s1:
    image: busybox:stable
    command: 'sh -c "exit 10"'
"""
        )

    async def given_plugin_initialized(self):
        self.default_env = Environment(Service('s1'), description=DEFAULT_ENV_DESCRIPTION)

        class _VedroUberCompose(VedroUberCompose):
            enabled = True
            default_env = self.default_env
            compose_cfgs = {
                DEFAULT_COMPOSE: ComposeConfig(compose_files='docker-compose.yaml'),
            }

        self.plugin = VedroUberComposePlugin(
            config=_VedroUberCompose,
            client=UberCompose(
                log_policy=LogPolicy.VERBOSE,
                health_policy=UpHealthPolicy(
                    service_up_check_attempts=3,
                    service_up_check_delay_s=1,
                    pre_check_delay_s=1
                )
            )
        )

    async def given_plugin_arg_parsed(self):
        self.args = ArgParsedEvent(
            args=Namespace(
                uc_default=None,
                uc_fr=None,
                uc_ju=None,
                uc_external_services=None,
                uc_v=None,
                uc_env=None,
            )
        )
        self.plugin.handle_arg_parsed(self.args)

    async def given_startup_event(self):
        self.scenarios = [
            make_scenario(env=self.default_env),
        ]
        self.startup_event = StartupEvent(
            scheduler=MonotonicScenarioScheduler(self.scenarios),
        )

    async def given_scenario_order_mocked(self):
        self.plugin._global_config = Mock()
        self.plugin._global_config.Registry = Mock()
        self.plugin._global_config.Registry.ScenarioOrderer = Mock()
        self.plugin._global_config.Registry.ScenarioOrderer.register = Mock(return_value=None)

    async def when_vedro_fires_startup_event(self):
        with catched(SystemExit) as self.exc_info:
            await self.plugin.handle_prepare_scenarios(self.startup_event)

    async def then_it_should_exit_with_code_75(self):
        assert self.exc_info.type is SystemExit
        assert self.exc_info.value.code == 75
