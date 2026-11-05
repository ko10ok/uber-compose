from typing import Type

from vedro.core import ConfigType
from vedro.core import Dispatcher
from vedro.core import Plugin
from vedro.core import PluginConfig
from vedro.events import ArgParseEvent
from vedro.events import ArgParsedEvent
from vedro.events import ConfigLoadedEvent
from vedro.events import StartupEvent

from uber_compose.parallel_plugin.grouper import build_execution_plan_from_scheduler
from uber_compose.parallel_plugin.grouping import env_group_key
from uber_compose.parallel_plugin.runner import ParallelScenarioRunner
from uber_compose.parallel_plugin.worker_api import get_worker_groups
from uber_compose.parallel_plugin.worker_api import get_workers_total
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
        self._refresh_worker_state()

    def _refresh_worker_state(self) -> None:
        self._is_worker = is_parallel_worker_process()
        self._workers_total = get_workers_total()
        self._worker_groups = get_worker_groups()

    def subscribe(self, dispatcher: Dispatcher) -> None:
        if not self._enabled:
            return

        dispatcher.listen(ConfigLoadedEvent, self.on_config_loaded) \
            .listen(ArgParseEvent, self.handle_arg_parse, priority=-100) \
            .listen(ArgParsedEvent, self.handle_arg_parsed, priority=-100) \
            .listen(StartupEvent, self.handle_prepare_scenarios, priority=-100)

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
        self._refresh_worker_state()
        self._maybe_register_runner()

    def _maybe_register_runner(self) -> None:
        if self._parallel <= 1 or self._is_worker or self._global_config is None:
            return
        dispatcher = self._global_config.Registry.Dispatcher()
        self._global_config.Registry.ScenarioRunner.register(
            resolver=lambda: ParallelScenarioRunner(
                dispatcher=dispatcher,
                grouping_key=self._grouping_key,
            ),
            registrant=self,
        )

    async def handle_prepare_scenarios(self, event: StartupEvent) -> None:
        self._refresh_worker_state()

        if self._is_worker:
            await ignore_foreign_scenarios(
                event.scheduler,
                self._worker_groups,
                self._grouping_key,
            )
            return

        if self._parallel <= 1:
            return

        plan = await build_execution_plan_from_scheduler(
            event.scheduler,
            self._parallel,
            self._grouping_key,
        )
        set_execution_plan(plan)


class VedroUberComposeParallel(PluginConfig):
    plugin = VedroUberComposeParallelPlugin

    enabled = False

    parallel: int = 1

    grouping_key = env_group_key


__all__ = ("VedroUberComposeParallel", "VedroUberComposeParallelPlugin",)
