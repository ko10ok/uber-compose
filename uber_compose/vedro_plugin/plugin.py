import sys
from typing import Type
from typing import Union
from uuid import uuid4

import vedro.events
from rich.text import Text
from vedro.core import ConfigType
from vedro.core import Dispatcher
from vedro.core import Plugin
from vedro.core import PluginConfig
from vedro.events import ArgParseEvent
from vedro.events import ArgParsedEvent
from vedro.events import ConfigLoadedEvent
from vedro.events import ScenarioRunEvent
from vedro.events import StartupEvent

from uber_compose import SystemUberCompose
from uber_compose.output.styles import Style
from uber_compose import Environment
from uber_compose.core.constants import Constants
from uber_compose.core.sequence_run_types import ComposeConfig
from uber_compose.env_description.env_types import DEFAULT_ENV_DESCRIPTION
from uber_compose.env_description.env_types import OverridenService
from uber_compose.helpers.health_policy import UpHealthPolicy
from uber_compose.output.console import LogPolicy
from uber_compose.output.console import Logger
from uber_compose.uber_compose import TheUberCompose as TheUberCompose
from uber_compose.vedro_plugin.helpers.scenario_ordering import EnvTagsOrderer
from uber_compose.vedro_plugin.helpers.scenario_tag_processing import extract_scenario_config
from uber_compose.vedro_plugin.helpers.scenario_tag_processing import extract_scenarios_configs_set
from uber_compose.vedro_plugin.helpers.scenario_tag_processing import ignore_unsuitable
from uber_compose.vedro_plugin.helpers.test_env_vars_setter import setup_env_for_tests

DEFAULT_COMPOSE = 'default'

class VedroUberComposePlugin(Plugin):
    def __init__(self, config: Type["VedroUberCompose"], client: SystemUberCompose = None) -> None:
        super().__init__(config)
        self._enabled = config.enabled
        if config.default_env:
            assert config.default_env._description == DEFAULT_ENV_DESCRIPTION, 'default_env must have description set to DEFAULT_ENV_DESCRIPTION'
        self._default_env: Environment = config.default_env

        # cli args
        self._compose_configs: dict[str, ComposeConfig] = config.compose_cfgs
        assert DEFAULT_COMPOSE in self._compose_configs, \
            'Need to set up at least compose_cfgs = {DEFAULT_COMPOSE: ComposeConfig(...)} config'
        self._compose_choice: Union[ComposeConfig, None] = self._compose_configs[DEFAULT_COMPOSE]

        self._force_restart = False
        self._just_up = False
        self._logging_policy = None
        self._health_policy = config.health_policy
        self._logger = Logger(self._logging_policy, Constants())

        self._uc_external_services: list[OverridenService] = None
        self._uc_env: str = None
        self._uber_compose_client = client

        self.run_id = str(uuid4())[:8]


    def subscribe(self, dispatcher: Dispatcher) -> None:
        if not self._enabled:
            return

        dispatcher.listen(ConfigLoadedEvent, self.on_config_loaded) \
            .listen(vedro.events.ArgParseEvent, self.handle_arg_parse) \
            .listen(vedro.events.ArgParsedEvent, self.handle_arg_parsed) \
            .listen(vedro.events.StartupEvent, self.handle_prepare_scenarios) \
            .listen(vedro.events.ScenarioRunEvent, self.handle_pre_run_scenario)

    def on_config_loaded(self, event: ConfigLoadedEvent) -> None:
        self._global_config: ConfigType = event.config

    async def handle_prepare_scenarios(self, event: StartupEvent) -> None:
        if self._uber_compose_client is None:
            self._uber_compose_client = TheUberCompose(
                log_policy=self._logging_policy,
                health_policy=self._health_policy,
                run_id=self.run_id,
            )

        if self._uc_env:
            await ignore_unsuitable(event.scheduler, self._uc_env)

        needed_configs = await extract_scenarios_configs_set(event.scheduler)
        if not needed_configs:
            return

        # If no parallelism allowed, reorder scenarios by env tags
        if len(needed_configs) > self._compose_choice.parallel_env_limit:
            self._global_config.Registry.ScenarioOrderer.register(EnvTagsOrderer, self)

        # Up all needed env simultaneously if parallelism allowed
        try:
            if self._compose_choice.parallel_env_limit >= len(needed_configs):
                for env_config in list(needed_configs):
                    if env_config == None:
                        env_config = self._default_env
                    await self._uber_compose_client.up(
                        config_template=env_config,
                        compose_files=self._compose_choice.compose_files,
                        parallelism_limit=self._compose_choice.parallel_env_limit,
                        force_restart=self._force_restart,
                        services_override=self._uc_external_services,
                    )
        except Exception as e:
            self._logger.stage(
                Text(
                    f'Error while starting environment: {e}\nExiting test environment preparation.',
                    style=Style.bad
                )
            )
            sys.exit(75)

        if self._just_up:
            self._logger.stage(
                Text(
                    f'Environment has been started successfully. Exiting as requested.',
                    style=Style.good
                )
            )
            sys.exit(0)

    async def handle_pre_run_scenario(self, event: ScenarioRunEvent):
        env_config = await extract_scenario_config(event.scenario_result.scenario)

        if env_config == None:
            env_config = self._default_env

        previous_release_id = self._uber_compose_client.last_release_id

        ready_env = await self._uber_compose_client.up(
            config_template=env_config,
            compose_files=self._compose_choice.compose_files,
            parallelism_limit=self._compose_choice.parallel_env_limit,
            services_override=self._uc_external_services,
        )

        setup_env_for_tests(ready_env.env, self._uc_external_services, self._uber_compose_client.run_id)

        env_restarted = previous_release_id is not None and previous_release_id != ready_env.release_id
        if env_restarted:
            scenario = event.scenario_result.scenario._orig_scenario
            if hasattr(scenario, 'on_env_restarted'):
                await scenario().on_env_restarted()

    def handle_arg_parse(self, event: ArgParseEvent) -> None:
        group = event.arg_parser.add_argument_group("Uber Compose")

        for choice_name, config in self._compose_configs.items():
            default_text = '[set by default]' if choice_name == DEFAULT_COMPOSE else ''
            group.add_argument(f"--uc-{choice_name}",
                               action='store_true',
                               help=f"Choose compose config {default_text}: {config}")

        group.add_argument("--uc-fr",
                           action='store_true',
                           help="Force restart env")

        group.add_argument("--uc-ju",
                           action='store_true',
                           help="Just up the environment and exit (no scenarios will be run)")

        group.add_argument("--uc-env",
                           type=str,
                           help="Filter by environment name/description")

        group.add_argument("--uc-v",
                           type=str,
                           nargs='?',
                           const='VERBOSE',
                           choices=list(LogPolicy.presets().keys()),
                           help="Increase logging verbosity")
        overridden_services_names = [
            overriden_service.service.name
            for overriden_service in [
                overriden_service
                for choice_name, config in self._compose_configs.items()
                if config.overridden_services
                for overriden_service in config.overridden_services
            ]
        ]

        group.add_argument("--uc-external-services",
                           type=str,
                           nargs='?',
                           const='ALL',
                           choices=list([
                               'ALL',
                               *overridden_services_names,
                           ]),
                           help="Run with overriden to external services")


    def handle_arg_parsed(self, event: ArgParsedEvent) -> None:
        for choice_name, config in self._compose_configs.items():
            if getattr(event.args, f'uc_{choice_name}'):
                self._compose_choice = config

        if event.args.uc_fr:
            self._force_restart = event.args.uc_fr

        if event.args.uc_ju:
            self._just_up = event.args.uc_ju

        if event.args.uc_env:
            self._uc_env = event.args.uc_env

        if event.args.uc_external_services:
            if event.args.uc_external_services == 'ALL':
                self._uc_external_services = [
                    overriden_service for overriden_service in self._compose_choice.overridden_services
                ]
            else:
                self._uc_external_services = [
                    overriden_service for overriden_service in self._compose_choice.overridden_services
                    if overriden_service.service.name in self._uc_external_services
                ]

        if event.args.uc_v is None:
            self._logging_policy = LogPolicy.DEFAULT
        else:
            level = str(event.args.uc_v).upper()
            if level in LogPolicy.presets().keys():
                self._logging_policy = LogPolicy.presets().get(level)
            else:
                raise ValueError(
                    f"Unknown logging policy '{event.args.uc_v}'. "
                    f"Available options: {', '.join(LogPolicy.presets().keys())}"
                )

        # TODO override parallelism


class VedroUberCompose(PluginConfig):
    plugin = VedroUberComposePlugin

    # Enables plugin
    enabled = False

    # Default env which should be used if not set in test. All services from compose files if not set
    default_env: Environment = None

    # ComposeConfig set of compose files and default parallelism restrictions
    compose_cfgs: dict[str, ComposeConfig] = None

    # Retries for health
    health_policy: UpHealthPolicy = UpHealthPolicy(
        wait_for_healthy_in_between=True,
        wait_for_healthy_after_all=True,
        service_up_check_attempts=100,
        service_up_check_delay_s=3
    )
