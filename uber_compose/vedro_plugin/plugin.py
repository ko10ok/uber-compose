import sys
from typing import Type
from typing import Union
from uuid import uuid4

from rich.text import Text
from vedro.core import ConfigType
from vedro.core import Dispatcher
from vedro.core import Plugin
from vedro.core import PluginConfig
import vedro.events
from vedro.events import ArgParseEvent
from vedro.events import ArgParsedEvent
from vedro.events import ConfigLoadedEvent
from vedro.events import ScenarioRunEvent
from vedro.events import StartupEvent

from uber_compose import Environment
from uber_compose import SystemUberCompose
from uber_compose.core.constants import Constants
from uber_compose.core.sequence_run_types import ComposeConfig
from uber_compose.core.utils.compose_instance_cfg import get_stable_env_id
from uber_compose.env_description.env_types import DEFAULT_ENV_DESCRIPTION
from uber_compose.env_description.env_types import OverridenService
from uber_compose.helpers.current_env import CurrentEnvContext
from uber_compose.helpers.current_env import get_run_depth
from uber_compose.helpers.current_env import set_current_env_context
from uber_compose.helpers.health_policy import UpHealthPolicy
from uber_compose.output.console import LogPolicy
from uber_compose.output.console import Logger
from uber_compose.output.styles import Style
from uber_compose.parallel_plugin.grouping import env_group_key_for
from uber_compose.parallel_plugin.planner import build_run_plan
from uber_compose.parallel_plugin.planner import render_plan
from uber_compose.parallel_plugin.worker_api import get_env_replicas_total
from uber_compose.parallel_plugin.worker_api import get_execution_plan
from uber_compose.parallel_plugin.worker_api import get_mt_enabled
from uber_compose.parallel_plugin.worker_api import get_namespace_map
from uber_compose.parallel_plugin.worker_api import get_worker_groups
from uber_compose.parallel_plugin.worker_api import get_worker_id
from uber_compose.parallel_plugin.worker_api import get_worker_replica_index
from uber_compose.parallel_plugin.worker_api import get_workers_per_env_override
from uber_compose.parallel_plugin.worker_api import get_workers_total
from uber_compose.parallel_plugin.worker_api import is_parallel_worker_process
from uber_compose.parallel_plugin.worker_api import set_workers_per_env
from uber_compose.uber_compose import TheUberCompose as TheUberCompose
from uber_compose.utils.docker_compose_files_path import get_absolute_compose_files
from uber_compose.utils.services_construction import make_default_environment
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
            assert config.default_env._description == DEFAULT_ENV_DESCRIPTION, (
                'default_env must have description set to DEFAULT_ENV_DESCRIPTION'
            )
        self._default_env: Environment = config.default_env

        # cli args
        self._compose_configs: dict[str, ComposeConfig] = config.compose_cfgs
        assert DEFAULT_COMPOSE in self._compose_configs, \
            'Need to set up at least compose_cfgs = {DEFAULT_COMPOSE: ComposeConfig(...)} config'
        self._compose_choice: Union[ComposeConfig, None] = self._compose_configs[DEFAULT_COMPOSE]
        self._compose_choice_name = DEFAULT_COMPOSE

        self._force_restart = False
        self._just_up = False
        self._melt_down = False
        self._logging_policy = None
        self._health_policy = config.health_policy
        self._logger = Logger(self._logging_policy, Constants())

        self._uc_external_services: list[OverridenService] = None
        self._uc_env: str = None
        self._plan_level = None
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
        self._global_config.Registry.ScenarioOrderer.register(EnvTagsOrderer, self)

    async def handle_prepare_scenarios(self, event: StartupEvent) -> None:
        if self._uc_env:
            await ignore_unsuitable(event.scheduler, self._uc_env)

        if self._plan_level is not None:
            plan = await build_run_plan(
                event.scheduler,
                compose_config=self._compose_config_name(),
                compose_files=self._compose_choice.compose_files,
                default_env=self._resolve_plan_default_env(),
                workers_per_env=self._compose_choice.workers_per_env,
                default_workers_per_env=self._compose_choice.default_workers_per_env,
                max_concurrent_envs=self._compose_choice.max_concurrent_envs,
                uc_mt_enabled=get_mt_enabled(),
                workers_per_env_override=get_workers_per_env_override(),
            )
            print(render_plan(plan, level=self._plan_level), flush=True)
            sys.exit(0)

        if self._uber_compose_client is None:
            self._uber_compose_client = TheUberCompose(
                log_policy=self._logging_policy,
                health_policy=self._health_policy,
                run_id=self.run_id,
            )

        if is_parallel_worker_process():
            return

        needed_configs = await extract_scenarios_configs_set(event.scheduler)
        needed_group_keys = {
            env_group_key_for(config_template)
            for config_template in needed_configs
        }

        plan = get_execution_plan()
        if plan is not None:
            try:
                await self._up_plan_environments(plan, needed_group_keys)
                if self._melt_down:
                    await self._melt_down_plan_environments(plan, needed_group_keys)
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
                        'Environment has been started successfully. Exiting as requested.',
                        style=Style.good
                    )
                )
                sys.exit(0)
            return

        if not needed_configs:
            if self._just_up:
                self._logger.stage(
                    Text(
                        'No environments to start. Exiting as requested.',
                        style=Style.good
                    )
                )
                sys.exit(0)
            return

        # Up all needed env simultaneously if parallelism allowed
        try:
            if self._compose_choice.workers_per_env is not None:
                await self._uber_compose_client.prepare_parallel_environments(
                    config_templates=needed_configs,
                    compose_files=self._compose_choice.compose_files,
                    workers_per_env=self._compose_choice.workers_per_env,
                    default_workers_per_env=self._compose_choice.default_workers_per_env,
                    force_restart=self._force_restart,
                    services_override=self._uc_external_services,
                )
            elif self._compose_choice.max_concurrent_envs >= len(needed_configs):
                for env_config in list(needed_configs):
                    if self._default_env is None and env_config is None:
                        self._logger.stage(
                            Text(
                                '[UberCompose] Warning: some scenarios has no "env" field set.\n'
                                'Consider adding "env = Envs.DEFAULT" to your scenario.',
                                style=Style.suspicious
                            )
                        )

                    if env_config is None:
                        env_config = self._default_env

                    await self._uber_compose_client.up(
                        config_template=env_config,
                        compose_files=self._compose_choice.compose_files,
                        parallelism_limit=self._compose_choice.max_concurrent_envs,
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
                    'Environment has been started successfully. Exiting as requested.',
                    style=Style.good
                )
            )
            sys.exit(0)

    def _compose_config_name(self) -> str:
        return self._compose_choice_name

    def _resolve_plan_default_env(self) -> Environment | None:
        if self._default_env is not None:
            return self._default_env
        compose_files = self._compose_choice.compose_files
        if not compose_files:
            return None
        constants = Constants()
        return make_default_environment(
            compose_files=get_absolute_compose_files(
                compose_files,
                constants.in_docker_project_root_path,
            ),
        )

    async def _up_plan_environments(self, plan, allowed_group_keys: set[str] | None = None) -> None:
        parallelism_limit = max(plan.workers_total, 2)
        started_env_ids = set()
        for assignment in plan.assignments:
            for group_key, env_id in assignment.namespace_map.items():
                if allowed_group_keys is not None and group_key not in allowed_group_keys:
                    continue
                if env_id in started_env_ids:
                    continue
                started_env_ids.add(env_id)
                config_template = plan.env_templates.get(group_key)
                if config_template is None:
                    config_template = self._default_env
                await self._uber_compose_client.up(
                    config_template=config_template,
                    compose_files=self._compose_choice.compose_files,
                    parallelism_limit=parallelism_limit,
                    force_restart=self._force_restart,
                    services_override=self._uc_external_services,
                    env_id=env_id,
                )

    async def _melt_down_plan_environments(self, plan, allowed_group_keys: set[str] | None = None) -> None:
        desired_by_group: dict[str, set[str]] = {}
        for assignment in plan.assignments:
            for group_key, env_id in assignment.namespace_map.items():
                if allowed_group_keys is not None and group_key not in allowed_group_keys:
                    continue
                desired_by_group.setdefault(group_key, set()).add(env_id)

        for group_key, desired_env_ids in desired_by_group.items():
            config_template = plan.env_templates.get(group_key)
            if config_template is None:
                config_template = self._default_env
            await self._uber_compose_client.melt_down_extra_replicas(
                config_template=config_template,
                compose_files=self._compose_choice.compose_files,
                desired_env_ids=sorted(desired_env_ids),
                services_override=self._uc_external_services,
            )

    async def handle_pre_run_scenario(self, event: ScenarioRunEvent):
        scenario = event.scenario_result.scenario
        env_config = await extract_scenario_config(scenario)

        if self._default_env is None and env_config is None:
            self._logger.stage(
                Text(
                    f'[UberCompose] Warning: scenario "{scenario.path}" has no "env" field set.\n'
                    'Consider adding "env = Envs.DEFAULT" to your scenario.',
                    style=Style.suspicious
                )
            )

        if env_config is None:
            env_config = self._default_env

        if is_parallel_worker_process():
            env_id = self._resolve_worker_env_id(env_config)
            parallelism_limit = max(get_workers_total(), 2)
        else:
            env_id = None
            parallelism_limit = self._compose_choice.max_concurrent_envs

        ready_env = await self._uber_compose_client.up(
            config_template=env_config,
            compose_files=self._compose_choice.compose_files,
            parallelism_limit=parallelism_limit,
            services_override=self._uc_external_services,
            env_id=env_id,
        )

        set_current_env_context(CurrentEnvContext(
            env_id=ready_env.env_id,
            env=ready_env.env,
            worker_id=get_worker_id(),
            workers_total=get_workers_total(),
            replica_index=get_worker_replica_index(),
            replicas_total=get_env_replicas_total(),
            namespace=ready_env.env_id,
            groups=tuple(get_worker_groups() or ()),
            run_id=self._uber_compose_client.run_id,
            run_depth=get_run_depth(),
        ))
        setup_env_for_tests(ready_env.env, self._uc_external_services, self._uber_compose_client.run_id)

    def _resolve_worker_env_id(self, env_config):
        group_key = env_group_key_for(env_config)
        namespace_map = get_namespace_map()
        if group_key in namespace_map:
            return namespace_map[group_key]
        return get_stable_env_id(env_config, get_worker_id())

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

        group.add_argument("--uc-melt-down", "--uc-mt-md",
                           dest="uc_melt_down",
                           action='store_true',
                           default=False,
                           help="Down extra parallel env replicas above the required count")

        group.add_argument("--uc-mt-plan",
                           type=int,
                           nargs='?',
                           const=0,
                           choices=(0, 1, 2),
                           default=None,
                           help="Print the execution plan without starting anything")

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
                self._compose_choice_name = choice_name

        if event.args.uc_fr:
            self._force_restart = event.args.uc_fr

        if event.args.uc_ju:
            self._just_up = event.args.uc_ju

        self._melt_down = bool(getattr(event.args, 'uc_melt_down', False))

        if event.args.uc_env:
            self._uc_env = event.args.uc_env

        self._plan_level = getattr(event.args, 'uc_mt_plan', None)

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

        set_workers_per_env(
            self._compose_choice.workers_per_env,
            self._compose_choice.default_workers_per_env,
        )


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
