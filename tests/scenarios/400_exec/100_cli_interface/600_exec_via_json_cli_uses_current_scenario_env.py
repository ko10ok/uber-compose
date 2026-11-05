from argparse import Namespace
import json
from unittest.mock import Mock

from contexts.compose_file import compose_file
from contexts.isolated_project import isolated_constants
from contexts.isolated_project import isolated_project
from contexts.no_docker_containers import no_docker_containers
from d42 import schema
from helpers.vedro.scenario import make_scenario
import vedro
from vedro.core import MonotonicScenarioScheduler
from vedro.events import ArgParsedEvent
from vedro.events import StartupEvent

from uber_compose import CommandResult
from uber_compose import CommonJsonCli
from uber_compose import ComposeConfig
from uber_compose import DEFAULT_COMPOSE
from uber_compose import UpHealthPolicy
from uber_compose import VedroUberCompose
from uber_compose.env_description.env_types import DEFAULT_ENV_DESCRIPTION
from uber_compose.env_description.env_types import Env
from uber_compose.env_description.env_types import Environment
from uber_compose.env_description.env_types import Service
from uber_compose.helpers.current_env import reset_current_env_id
from uber_compose.uber_compose import UberCompose
from uber_compose.vedro_plugin.plugin import VedroUberComposePlugin


class Scenario(vedro.Scenario):
    subject = 'exec via json cli automatically uses current scenario environment'

    async def given_no_docker_containers(self):
        no_docker_containers()

    async def given_isolated_project(self):
        self.project = isolated_project()
        self.instance_files_root = self.project.tmp_envs_path
        self.constants = isolated_constants(self.project)

    async def given_current_env_reset_for_this_scenario(self):
        vedro.defer(reset_current_env_id)
        reset_current_env_id()

    async def given_compose_files(self):
        self.compose_files = 'docker-compose.yaml'
        compose_file(
            self.compose_files,
            content="""
version: "3"

services:
  s1:
    image: busybox:stable
    command: 'sh -c "trap : TERM INT; sleep 604800; wait"'
"""
        )

    async def given_plugin_with_two_namespaced_envs(self):
        self.default_env = Environment(
            Service('s1', Env({'ENV_MARKER': 'default'})),
            description=DEFAULT_ENV_DESCRIPTION,
        )

        class _VedroUberCompose(VedroUberCompose):
            enabled = True
            default_env = self.default_env
            compose_cfgs = {
                DEFAULT_COMPOSE: ComposeConfig(
                    compose_files='docker-compose.yaml',
                    parallel_env_limit=2,
                ),
            }

        self.plugin = VedroUberComposePlugin(
            config=_VedroUberCompose,
            client=UberCompose(
                cfg_constants=self.constants,
                health_policy=UpHealthPolicy(
                    service_up_check_attempts=3,
                    service_up_check_delay_s=1,
                    pre_check_delay_s=1,
                ),
            ),
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

    async def given_startup_event_with_two_different_envs(self):
        self.env_a = Environment(Service('s1', Env({'ENV_MARKER': 'a'})), description='env-a')
        self.env_b = Environment(Service('s1', Env({'ENV_MARKER': 'b'})), description='env-b')
        self.scenarios = [
            make_scenario(env=self.env_a),
            make_scenario(env=self.env_b),
        ]
        self.startup_event = StartupEvent(
            scheduler=MonotonicScenarioScheduler(self.scenarios),
        )

    async def given_scenario_order_mocked(self):
        self.plugin._global_config = Mock()
        self.plugin._global_config.Registry = Mock()
        self.plugin._global_config.Registry.ScenarioOrderer = Mock()
        self.plugin._global_config.Registry.ScenarioOrderer.register = Mock(return_value=None)

    async def given_vedro_fired_startup_event(self):
        await self.plugin.handle_prepare_scenarios(self.startup_event)

    async def given_command(self):
        self.cmd = 'echo {\\"level\\": \\"stdout\\", \\"MARKER\\":\\"$ENV_MARKER\\"}'

    async def when_first_scenario_starts_and_execs_via_json_cli(self):
        await self.plugin.handle_pre_run_scenario(self._scenario_run_event(self.scenarios[0]))
        self.result_a = await CommonJsonCli(cli_client=UberCompose(cfg_constants=self.constants, )).exec(
            container='s1',
            command=self.cmd,
        )

    async def when_second_scenario_starts_and_execs_via_json_cli(self):
        await self.plugin.handle_pre_run_scenario(self._scenario_run_event(self.scenarios[1]))
        self.result_b = await CommonJsonCli(cli_client=UberCompose(cfg_constants=self.constants, )).exec(
            container='s1',
            command=self.cmd,
        )

    async def then_first_scenario_exec_should_return_env_a_marker(self):
        assert isinstance(self.result_a, CommandResult)
        assert self.result_a.stdout == schema.list([
            schema.str(json.dumps({'level': 'stdout', 'MARKER': 'a'})),
        ])

    async def then_second_scenario_exec_should_return_env_b_marker(self):
        assert isinstance(self.result_b, CommandResult)
        assert self.result_b.stdout == schema.list([
            schema.str(json.dumps({'level': 'stdout', 'MARKER': 'b'})),
        ])

    def _scenario_run_event(self, scenario):
        event = Mock()
        event.scenario_result = Mock()
        event.scenario_result.scenario = scenario
        return event
