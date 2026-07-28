from unittest.mock import AsyncMock
from unittest.mock import Mock

import vedro

from helpers.vedro.scenario import make_scenario
from uber_compose import ComposeConfig
from uber_compose import DEFAULT_COMPOSE
from uber_compose import VedroUberCompose
from uber_compose.env_description.env_types import DEFAULT_ENV_DESCRIPTION
from uber_compose.env_description.env_types import Environment
from uber_compose.env_description.env_types import Service
from uber_compose.vedro_plugin.plugin import VedroUberComposePlugin


class Scenario(vedro.Scenario):
    subject = "warn when scenario has no env and warn_missing_env is enabled"

    def given_plugin_initialized(self):
        self.default_env = Environment(Service("s1"), description=DEFAULT_ENV_DESCRIPTION)

        class _VedroUberCompose(VedroUberCompose):
            enabled = True
            default_env = self.default_env
            warn_missing_env = True
            compose_cfgs = {
                DEFAULT_COMPOSE: ComposeConfig(compose_files="docker-compose.yml"),
            }

        self.plugin = VedroUberComposePlugin(config=_VedroUberCompose)
        self.plugin._logger = Mock()
        self.plugin._uber_compose_client = Mock()
        self.plugin._uber_compose_client.up = AsyncMock(return_value=Mock(env=self.default_env))

    def given_mocked_scenario_without_env(self):
        self.scenario = make_scenario()
        self.event = Mock()
        self.event.scenario_result = Mock(scenario=self.scenario)

    async def when_plugin_handles_scenario(self):
        await self.plugin.handle_pre_run_scenario(self.event)

    def then_it_should_warn(self):
        self.plugin._logger.stage.assert_called_once()
        warning_text = self.plugin._logger.stage.call_args.args[0].plain
        assert 'has no "env" field set' in warning_text

    def and_it_should_use_default_env(self):
        self.plugin._uber_compose_client.up.assert_awaited_once()
        call_kwargs = self.plugin._uber_compose_client.up.await_args.kwargs
        assert call_kwargs["config_template"] == self.default_env
