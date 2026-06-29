from argparse import Namespace
from unittest.mock import Mock

import vedro
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
from uber_compose.uber_compose import UberCompose
from uber_compose.vedro_plugin.plugin import VedroUberComposePlugin


class Scenario(vedro.Scenario):
    async def given_no_docker_containers(self):
        no_docker_containers()

    async def given_no_docker_compose_files(self):
        no_docker_compose_files()

    async def given_compose_files(self):
        self.compose_filename = 'docker-compose.yaml'
        compose_file(
            self.compose_filename,
            content="""
version: "3"
services:
  s2:
    image: busybox:stable
    command: 'sh -c "trap : TERM INT; sleep 604800; wait"'
"""
        )

    async def given_client(self):
        self.uber_compose_client = UberCompose()

    async def given_plugin_initialized(self):
        self.default_env = Environment(Service('s2'), description=DEFAULT_ENV_DESCRIPTION)

        class _VedroUberCompose(VedroUberCompose):
            enabled = True
            default_env = self.default_env
            compose_cfgs = {
                DEFAULT_COMPOSE: ComposeConfig(compose_files='docker-compose.yaml'),
            }

        self.plugin = VedroUberComposePlugin(config=_VedroUberCompose)

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
        self.env_a = Environment(Service('s2'), description='env_a')
        self.env_b = Environment(Service('s2'), description='env_b')

        self.scenario_a = make_scenario(env=self.env_a, with_env_restart_hook=True)
        self.scenario_b = make_scenario(env=self.env_b, with_env_restart_hook=True)

        self.startup_event = StartupEvent(
            scheduler=MonotonicScenarioScheduler([self.scenario_a, self.scenario_b]),
        )

    async def given_scenario_order_mocked(self):
        self.plugin._global_config = Mock()
        self.plugin._global_config.Registry = Mock()
        self.plugin._global_config.Registry.ScenarioOrderer = Mock()
        self.plugin._global_config.Registry.ScenarioOrderer.register = Mock(return_value=None)

    async def given_vedro_fired_startup_event(self):
        await self.plugin.handle_prepare_scenarios(self.startup_event)

    async def given_first_scenario_ran(self):
        self.run_event_a = Mock()
        self.run_event_a.scenario_result = Mock()
        self.run_event_a.scenario_result.scenario = self.scenario_a
        await self.plugin.handle_pre_run_scenario(self.run_event_a)

    async def when_second_scenario_runs(self):
        self.run_event_b = Mock()
        self.run_event_b.scenario_result = Mock()
        self.run_event_b.scenario_result.scenario = self.scenario_b
        await self.plugin.handle_pre_run_scenario(self.run_event_b)

    async def then_hook_should_be_called_on_env_restart(self):
        assert self.scenario_b._orig_scenario.on_env_restarted_called is True, \
            "on_env_restarted hook was not called when env restarted"

    async def and_hook_should_not_be_called_for_first_scenario(self):
        assert self.scenario_a._orig_scenario.on_env_restarted_called is False, \
            "on_env_restarted hook should not be called for first scenario"
