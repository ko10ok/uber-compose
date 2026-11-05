from argparse import Namespace
from unittest.mock import Mock

from contexts.compose_file import compose_file
from contexts.no_docker_compose_files import no_docker_compose_files
from contexts.no_docker_containers import no_docker_containers
from contexts.no_docker_containers import retrieve_all_docker_containers
from d42 import schema
from helpers.vedro.scenario import make_scenario
from schemas.docker import ContainerSchema
import vedro
from vedro.core import MonotonicScenarioScheduler
from vedro.events import ArgParsedEvent
from vedro.events import StartupEvent

from uber_compose import ComposeConfig
from uber_compose import DEFAULT_COMPOSE
from uber_compose import UpHealthPolicy
from uber_compose import VedroUberCompose
from uber_compose.env_description.env_types import DEFAULT_ENV_DESCRIPTION
from uber_compose.env_description.env_types import Environment
from uber_compose.env_description.env_types import Service
from uber_compose.helpers.labels import Label
from uber_compose.uber_compose import UberCompose
from uber_compose.vedro_plugin.plugin import VedroUberComposePlugin


class Scenario(vedro.Scenario):
    subject = 'up envs one by one when parallel_env_limit is less than needed env templates'

    async def given_no_docker_containers(self):
        no_docker_containers()

    async def given_no_docker_compose_files(self):
        no_docker_compose_files()

    async def given_compose_files(self):
        compose_file(
            'docker-compose.yaml',
            content="""
version: "3"

services:
  s1:
    image: busybox:stable
    command: 'sh -c "trap : TERM INT; sleep 604800; wait"'

  s2:
    image: busybox:stable
    command: 'sh -c "trap : TERM INT; sleep 604800; wait"'

  s3:
    image: busybox:stable
    command: 'sh -c "trap : TERM INT; sleep 604800; wait"'
"""
        )

    async def given_plugin_initialized_with_parallel_env_limit_less_than_needed(self):
        self.default_env = Environment(Service('s3'), description=DEFAULT_ENV_DESCRIPTION)

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

    async def given_startup_event_with_three_different_envs(self):
        self.env_a = Environment(Service('s1'), description='env-a')
        self.env_b = Environment(Service('s2'), description='env-b')
        self.env_c = Environment(Service('s3'), description='env-c')
        self.scenarios = [
            make_scenario(env=self.env_a),
            make_scenario(env=self.env_b),
            make_scenario(env=self.env_c),
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
        self.containers_after_startup = retrieve_all_docker_containers()

    async def when_first_scenario_runs(self):
        await self.plugin.handle_pre_run_scenario(self._scenario_run_event(self.scenarios[0]))
        self.containers_after_first_scenario = retrieve_all_docker_containers()

    async def when_second_scenario_runs(self):
        await self.plugin.handle_pre_run_scenario(self._scenario_run_event(self.scenarios[1]))
        self.containers_after_second_scenario = retrieve_all_docker_containers()

    async def when_third_scenario_runs(self):
        await self.plugin.handle_pre_run_scenario(self._scenario_run_event(self.scenarios[2]))
        self.containers_after_third_scenario = retrieve_all_docker_containers()

    async def then_startup_event_should_up_no_env(self):
        assert self.containers_after_startup == schema.list([])

    async def then_first_scenario_should_up_only_its_own_env(self):
        assert self.containers_after_first_scenario == schema.list([
            ContainerSchema % {
                'Labels': {
                    Label.TEMPLATE_SERVICE_NAME: 's1',
                },
            },
        ])

    async def then_second_scenario_should_add_its_own_env_keeping_the_first(self):
        assert self.containers_after_second_scenario == schema.list([
            ...,
            ContainerSchema % {
                'Labels': {
                    Label.TEMPLATE_SERVICE_NAME: 's1',
                },
            },
            ...,
        ])
        assert self.containers_after_second_scenario == schema.list([
            ...,
            ContainerSchema % {
                'Labels': {
                    Label.TEMPLATE_SERVICE_NAME: 's2',
                },
            },
            ...,
        ])
        assert len(self.containers_after_second_scenario) == 2

    async def then_third_scenario_should_add_its_own_env_keeping_the_previous(self):
        for service_name in ('s1', 's2', 's3'):
            assert self.containers_after_third_scenario == schema.list([
                ...,
                ContainerSchema % {
                    'Labels': {
                        Label.TEMPLATE_SERVICE_NAME: service_name,
                    },
                },
                ...,
            ])
        assert len(self.containers_after_third_scenario) == 3

    def _scenario_run_event(self, scenario):
        event = Mock()
        event.scenario_result = Mock()
        event.scenario_result.scenario = scenario
        return event
