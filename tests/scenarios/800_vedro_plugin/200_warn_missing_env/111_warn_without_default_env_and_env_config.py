from unittest.mock import AsyncMock
from unittest.mock import Mock

import vedro

from helpers.vedro.scenario import make_scenario
from uber_compose import ComposeConfig
from uber_compose import DEFAULT_COMPOSE
from uber_compose import VedroUberCompose
from uber_compose.vedro_plugin.plugin import VedroUberComposePlugin


class Scenario(vedro.Scenario):
    subject = "warn without default_env and env_config"

    def given_plugin_initialized_without_default_env(self):
        class _VedroUberCompose(VedroUberCompose):
            enabled = True
            compose_cfgs = {
                DEFAULT_COMPOSE: ComposeConfig(compose_files="docker-compose.yml"),
            }

        self.plugin = VedroUberComposePlugin(config=_VedroUberCompose)
        self.plugin._logger = Mock()
        self.plugin._uber_compose_client = Mock()
        self.plugin._uber_compose_client.up = AsyncMock(return_value=Mock(env=Mock()))

    def given_mocked_scenario_without_env_config(self):
        self.scenario = make_scenario()
        self.event = Mock()
        self.event.scenario_result = Mock(scenario=self.scenario)

    async def when_plugin_handles_scenario(self):
        await self.plugin.handle_pre_run_scenario(self.event)

    def then_it_should_warn(self):
        self.plugin._logger.stage.assert_called_once()
        assert 'has no "env" field set' in self.plugin._logger.stage.call_args.args[0].plain

    def and_it_should_pass_no_env_to_uber_compose(self):
        self.plugin._uber_compose_client.up.assert_awaited_once()
        call_kwargs = self.plugin._uber_compose_client.up.await_args.kwargs
        assert call_kwargs["config_template"] is None
