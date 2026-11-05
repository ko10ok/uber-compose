import json
import sys
from typing import Type

from vedro.core import ConfigType
from vedro.core import Dispatcher
from vedro.core import Plugin
from vedro.core import PluginConfig
from vedro.events import ArgParseEvent
from vedro.events import ArgParsedEvent
from vedro.events import ConfigLoadedEvent
from vedro.events import ScenarioReportedEvent
from vedro.events import StartupEvent

from uber_compose.env_description.env_types import DEFAULT_ENV_DESCRIPTION
from uber_compose.parallel_plugin.details import serialize_result_details
from uber_compose.parallel_plugin.grouper import build_execution_plan_from_scheduler
from uber_compose.parallel_plugin.grouper import build_replica_execution_plan
from uber_compose.parallel_plugin.grouper import collect_group_counts
from uber_compose.parallel_plugin.grouping import env_group_key
from uber_compose.parallel_plugin.grouping import env_group_key_for
from uber_compose.parallel_plugin.grouping import scenario_env
from uber_compose.parallel_plugin.runner import ParallelScenarioRunner
from uber_compose.parallel_plugin.worker_api import get_env_parallelism
from uber_compose.parallel_plugin.worker_api import get_env_replicas_total
from uber_compose.parallel_plugin.worker_api import get_worker_groups
from uber_compose.parallel_plugin.worker_api import get_worker_replica_index
from uber_compose.parallel_plugin.worker_api import is_parallel_worker_process
from uber_compose.parallel_plugin.worker_api import set_execution_plan
from uber_compose.parallel_plugin.worker_filter import ignore_foreign_scenarios


class VedroUberComposeParallelPlugin(Plugin):
    def __init__(self, config: Type["VedroUberComposeParallel"]) -> None:
        super().__init__(config)
        self._enabled = config.enabled
        self._grouping_key = config.grouping_key or env_group_key
        self._parallel = max(int(config.parallel or 1), 1)
        self._global_config: ConfigType | None = None
        self._runner_registered = False
        self._capture_output = False
        self._capture_limit = None
        self._worker_timeout = config.worker_timeout
        self._worker_concurrency = config.worker_concurrency
        self._protocol_stdout = sys.stdout
        self._refresh_worker_state()

    def _refresh_worker_state(self) -> None:
        self._is_worker = is_parallel_worker_process()
        self._worker_groups = get_worker_groups()
        self._worker_replica_index = get_worker_replica_index()
        self._env_replicas_total = get_env_replicas_total()

    def subscribe(self, dispatcher: Dispatcher) -> None:
        if not self._enabled:
            return

        dispatcher.listen(ConfigLoadedEvent, self.on_config_loaded) \
            .listen(ArgParseEvent, self.handle_arg_parse, priority=-100) \
            .listen(ArgParsedEvent, self.handle_arg_parsed, priority=-100) \
            .listen(StartupEvent, self.handle_prepare_scenarios, priority=-100)

        if self._is_worker:
            dispatcher.listen(ScenarioReportedEvent, self.emit_scenario_details, priority=-50)

    def on_config_loaded(self, event: ConfigLoadedEvent) -> None:
        self._global_config = event.config

    def handle_arg_parse(self, event: ArgParseEvent) -> None:
        group = event.arg_parser.add_argument_group("Uber Compose Parallel")
        group.add_argument("--uc-parallel",
                           type=int,
                           default=None,
                           help="Number of parallel workers (1 keeps the sequential run)")

    def handle_arg_parsed(self, event: ArgParsedEvent) -> None:
        parallel = getattr(event.args, 'uc_parallel', None)
        if parallel:
            self._parallel = max(int(parallel), 1)
        self._capture_output = bool(getattr(event.args, 'capture_output', False))
        self._capture_limit = getattr(event.args, 'capture_limit', None)
        self._refresh_worker_state()

    def emit_scenario_details(self, event: ScenarioReportedEvent) -> None:
        result = event.aggregated_result
        payload = {
            'event': 'uc_scenario_details',
            'scenario': {'id': result.scenario.unique_id},
            **serialize_result_details(result),
        }
        self._protocol_stdout.write(json.dumps(payload) + '\n')
        self._protocol_stdout.flush()

    async def handle_prepare_scenarios(self, event: StartupEvent) -> None:
        self._refresh_worker_state()

        if self._is_worker:
            await ignore_foreign_scenarios(
                event.scheduler,
                self._worker_groups,
                self._grouping_key,
                replica_index=self._worker_replica_index,
                replicas_total=self._env_replicas_total,
            )
            return

        plan = await self._build_plan(event)
        if plan is None or plan.workers_total <= 1:
            return

        set_execution_plan(plan)
        self._register_runner()

    async def _build_plan(self, event: StartupEvent):
        env_parallelism = get_env_parallelism()
        if env_parallelism is not None:
            return await self._build_replica_plan(event, env_parallelism)
        if self._parallel <= 1:
            return None
        return await build_execution_plan_from_scheduler(
            event.scheduler,
            self._parallel,
            self._grouping_key,
        )

    async def _build_replica_plan(self, event: StartupEvent, env_parallelism):
        counts_by_description, default_replicas = env_parallelism
        group_counts = await collect_group_counts(event.scheduler, self._grouping_key)
        group_envs = {}
        namespace_counts = {}

        async for scenario in event.scheduler:
            if scenario.is_skipped():
                continue
            env = scenario_env(scenario)
            group_key = env_group_key_for(env)
            template = None if env is None or env.description == DEFAULT_ENV_DESCRIPTION else env
            group_envs[group_key] = template
            description = template.description if template is not None else DEFAULT_ENV_DESCRIPTION
            namespace_counts[group_key] = counts_by_description.get(description, default_replicas)

        return build_replica_execution_plan(
            group_counts=group_counts,
            group_envs=group_envs,
            namespace_counts=namespace_counts,
            default_replicas=default_replicas,
        )

    def _register_runner(self) -> None:
        if self._runner_registered or self._is_worker or self._global_config is None:
            return
        dispatcher = self._global_config.Registry.Dispatcher()
        self._global_config.Registry.ScenarioRunner.register(
            resolver=lambda: ParallelScenarioRunner(
                dispatcher=dispatcher,
                grouping_key=self._grouping_key,
                capture_output=self._capture_output,
                capture_limit=self._capture_limit,
                worker_timeout=self._worker_timeout,
                worker_concurrency=self._worker_concurrency,
            ),
            registrant=self,
        )
        self._runner_registered = True


class VedroUberComposeParallel(PluginConfig):
    plugin = VedroUberComposeParallelPlugin

    enabled = False

    parallel: int = 1

    worker_timeout: float | None = None

    worker_concurrency: int | None = None

    grouping_key = env_group_key


__all__ = ("VedroUberComposeParallel", "VedroUberComposeParallelPlugin",)
