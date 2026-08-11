from unittest.mock import AsyncMock
from unittest.mock import Mock

import vedro
from vedro.core import MonotonicScenarioScheduler
from vedro.events import StartupEvent

from helpers.vedro.scenario import make_scenario
from uber_compose import ComposeConfig
from uber_compose import DEFAULT_COMPOSE
from uber_compose import VedroUberCompose
from uber_compose.env_description.env_types import Environment
from uber_compose.env_description.env_types import Service
from uber_compose.vedro_plugin.plugin import VedroUberComposePlugin


class Scenario(vedro.Scenario):
    def given_plugin_initialized_without_default_env(self):
        class _VedroUberCompose(VedroUberCompose):
            enabled = True
            compose_cfgs = {
                DEFAULT_COMPOSE: ComposeConfig(compose_files="docker-compose.yml"),
            }

        self.plugin = VedroUberComposePlugin(config=_VedroUberCompose)
        self.plugin._logger = Mock()
        self.plugin._uber_compose_client = Mock()
        self.ready_env = Environment(Service("s1"), description="CUSTOM")
        self.plugin._uber_compose_client.up = AsyncMock(return_value=Mock(env=self.ready_env))

    def given_mocked_startup_scenario_without_env_config(self):
        self.scenarios = [make_scenario()]
        self.startup_event = StartupEvent(
            scheduler=MonotonicScenarioScheduler(self.scenarios),
        )

    async def when_plugin_handles_startup(self):
        await self.plugin.handle_prepare_scenarios(self.startup_event)

    def then_it_should_warn(self):
        self.plugin._logger.stage.assert_called_once()
        assert self.plugin._logger.stage.call_args.args[0].plain == (
            '[UberCompose] Warning: some scenarios has no "env" field set.\n'
            'Consider adding "env = Envs.DEFAULT" to your scenario.'
        )

    def and_it_should_pass_no_env_to_uber_compose(self):
        self.plugin._uber_compose_client.up.assert_awaited_once()
        call_kwargs = self.plugin._uber_compose_client.up.await_args.kwargs
        assert call_kwargs["config_template"] is None
