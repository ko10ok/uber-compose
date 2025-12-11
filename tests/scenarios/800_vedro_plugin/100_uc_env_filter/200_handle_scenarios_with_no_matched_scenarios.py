from argparse import Namespace
from operator import truediv

import vedro
from d42 import fake
from d42 import schema
from uber_compose.env_description.env_types import DEFAULT_ENV_DESCRIPTION
from vedro.core import MonotonicScenarioScheduler

from vedro.events import ArgParsedEvent
from vedro.events import StartupEvent

from helpers.vedro.scenario import describe_scenario
from helpers.vedro.scenario import make_scenario
from schemas.vedro.described_scenario import DescribedScenarios
from uber_compose import ComposeConfig
from uber_compose import DEFAULT_COMPOSE
from uber_compose import VedroUberCompose
from uber_compose.vedro_plugin.plugin import VedroUberComposePlugin

from contexts.compose_file import compose_file
from contexts.no_docker_compose_files import no_docker_compose_files
from contexts.no_docker_containers import no_docker_containers
from contexts.no_docker_containers import retrieve_all_docker_containers
from schemas.docker import ContainerSchema
from uber_compose.uber_compose import UberCompose
from uber_compose.env_description.env_types import Environment
from uber_compose.env_description.env_types import Service
from uber_compose.helpers.labels import Label


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

    # async def given_env_description(self):
    #     self.desc = fake(schema.str('') | schema.str('a a'))

    async def given_plugin_initialized(self):
        class _VedroUberCompose(VedroUberCompose):
            enabled = True
            default_env = Environment(Service('s2'), description=DEFAULT_ENV_DESCRIPTION)
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
                uc_env='blahblah',
            )
        )
        self.plugin.handle_arg_parsed(self.args)

    async def given_startup_event(self):
        self.scenarios = [
            make_scenario(),
        ]
        self.startup_event = StartupEvent(
            scheduler=MonotonicScenarioScheduler(self.scenarios),
        )

    async def when_vedro_fires_startup_event(self):
        await self.plugin.handle_prepare_scenarios(self.startup_event)

    async def then_it_should_filter_unmatched_scenarios(self):
        self.actual_result_scenarios = [
            describe_scenario(scenario) for scenario in self.scenarios
        ]
        assert list(self.startup_event.scheduler.scheduled) == []

    async def then_it_should_up_s2_only(self):
        self.containers = retrieve_all_docker_containers()
        assert self.containers == schema.list([])
