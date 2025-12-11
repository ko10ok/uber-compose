from argparse import Namespace
from unittest.mock import Mock

import vedro
from d42 import fake
from d42 import schema
from vedro.core import MonotonicScenarioScheduler
from vedro.events import ArgParsedEvent
from vedro.events import StartupEvent

from contexts.compose_file import compose_file
from contexts.no_docker_compose_files import no_docker_compose_files
from contexts.no_docker_containers import no_docker_containers
from contexts.no_docker_containers import retrieve_all_docker_containers
from helpers.vedro.scenario import describe_scenario
from helpers.vedro.scenario import make_scenario
from schemas.docker import ContainerSchema
from schemas.vedro.described_scenario import DescribedScenarios
from uber_compose import ComposeConfig
from uber_compose import DEFAULT_COMPOSE
from uber_compose import VedroUberCompose
from uber_compose.env_description.env_types import DEFAULT_ENV_DESCRIPTION
from uber_compose.env_description.env_types import Environment
from uber_compose.env_description.env_types import Service
from uber_compose.helpers.labels import Label
from uber_compose.uber_compose import UberCompose
from uber_compose.vedro_plugin.plugin import VedroUberComposePlugin


class Scenario(vedro.Scenario):
    async def no_docker_containers(self):
        no_docker_containers()

    async def no_docker_copose_files(self):
        no_docker_compose_files()

    async def given_compose_files(self):
        self.compose_filename_1 = 'docker-compose.yaml'
        compose_file(
            self.compose_filename_1,
            content="""
version: "3"

services:
  s1:
    image: busybox:stable
    command: 'sh -c "trap : TERM INT; sleep 604800; wait"'
"""
        )

        self.compose_filename_2 = 'docker-compose.dev.yaml'
        compose_file(
            self.compose_filename_2,
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
                DEFAULT_COMPOSE: ComposeConfig(compose_files='docker-compose.yaml:docker-compose.dev.yaml'),
            }

        self.plugin = VedroUberComposePlugin(config=_VedroUberCompose)

    async def given_plugin_arg_parsed(self):
        self.args = ArgParsedEvent(
            args=Namespace(
                uc_default=None,
                uc_fr=None,
                uc_external_services=None,
                uc_v=None,
                uc_env=None,
            )
        )
        self.plugin.handle_arg_parsed(self.args)

    async def given_env_description(self):
        self.desc = fake(schema.str('') | schema.str('a a'))

    async def given_startup_event(self):
        self.another_env = Environment(Service('s2'), description=self.desc)
        self.scenarios = [
            make_scenario(),
            make_scenario(env=self.default_env),
            make_scenario(env=self.another_env),
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

    async def given_mocked_scenario(self):
        self.run_scenario_event = Mock()
        self.run_scenario_event.scenario_result = Mock()
        self.run_scenario_event.scenario_result.scenario = self.scenarios[1]

    async def when_vedro_fires_scenario_run_event(self):
        await self.plugin.handle_pre_run_scenario(self.run_scenario_event)

    async def then_it_should_not_filter_any_scenarios(self):
        self.actual_result_scenarios = [
            describe_scenario(scenario) for scenario in self.scenarios
        ]
        assert list(self.startup_event.scheduler.scheduled) == [
            self.scenarios[0],
            self.scenarios[1],
            self.scenarios[2],
        ]

    async def then_it_should_up_s2_only(self):
        self.containers = retrieve_all_docker_containers()
        assert self.containers == schema.list([
            ContainerSchema % {
                'Labels': {
                    'com.docker.compose.service': 's2',
                    'com.docker.compose.project.config_files':
                        '/tmp/uc-envs/default_env_id/docker-compose.yaml,/tmp/uc-envs/default_env_id/docker-compose.dev.yaml',

                    Label.ENV_ID: 'default_env_id',
                    Label.ENV_DESCRIPTION: DEFAULT_ENV_DESCRIPTION,
                    Label.COMPOSE_FILES: ':'.join([
                        f'{self.compose_filename_1}',
                        f'{self.compose_filename_2}',
                    ]),
                    Label.COMPOSE_FILES_INSTANCE: ':'.join([
                        f'/tmp/uc-envs/default_env_id/{self.compose_filename_1}',
                        f'/tmp/uc-envs/default_env_id/{self.compose_filename_2}',
                    ]),
                },
            },
        ])
