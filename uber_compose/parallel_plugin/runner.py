import asyncio
import json
import os
import sys
from time import time
from typing import Any
from typing import Callable

from vedro.core import AggregatedResult
from vedro.core import Dispatcher
from vedro.core import MonotonicScenarioRunner
from vedro.core import Report
from vedro.core import ScenarioResult
from vedro.core import ScenarioRunner
from vedro.core import ScenarioScheduler
from vedro.core import VirtualScenario
from vedro.events import ScenarioFailedEvent
from vedro.events import ScenarioPassedEvent
from vedro.events import ScenarioReportedEvent
from vedro.events import ScenarioRunEvent
from vedro.events import ScenarioSkippedEvent

from uber_compose.parallel_plugin.types import WorkerAssignment
from uber_compose.parallel_plugin.worker_api import ENV_REPLICAS_TOTAL_ENV
from uber_compose.parallel_plugin.worker_api import NAMESPACE_MAP_ENV
from uber_compose.parallel_plugin.worker_api import WORKERS_TOTAL_ENV
from uber_compose.parallel_plugin.worker_api import WORKER_GROUPS_ENV
from uber_compose.parallel_plugin.worker_api import WORKER_ID_ENV
from uber_compose.parallel_plugin.worker_api import WORKER_REPLICA_INDEX_ENV
from uber_compose.parallel_plugin.worker_api import get_execution_plan

_TERMINAL_EVENTS = {
    'scenario_passed': (ScenarioPassedEvent, 'mark_passed'),
    'scenario_failed': (ScenarioFailedEvent, 'mark_failed'),
    'scenario_skipped': (ScenarioSkippedEvent, 'mark_skipped'),
}

_STATUS_MARKS = {
    'PASSED': 'mark_passed',
    'FAILED': 'mark_failed',
    'SKIPPED': 'mark_skipped',
}


class ParallelScenarioRunner(ScenarioRunner):
    def __init__(self, dispatcher: Dispatcher, grouping_key: Callable[[VirtualScenario], str]) -> None:
        self._dispatcher = dispatcher
        self._grouping_key = grouping_key

    async def run(self, scheduler: ScenarioScheduler, **kwargs: Any) -> Report:
        plan = get_execution_plan()
        if plan is None or plan.workers_total <= 1:
            return await self._run_sequentially(scheduler, **kwargs)

        scenarios = {scenario.unique_id: scenario for scenario in scheduler.discovered}
        scenario_paths = sorted({str(scenario.path) for scenario in scheduler.scheduled})
        if not scenario_paths:
            return Report()

        aggregated: dict[str, AggregatedResult] = {}
        fire_lock = asyncio.Lock()

        workers = [
            self._run_worker(
                assignment=assignment,
                workers_total=plan.workers_total,
                scenario_paths=scenario_paths,
                scenarios=scenarios,
                aggregated=aggregated,
                fire_lock=fire_lock,
            )
            for assignment in plan.assignments
            if assignment.groups
        ]
        await asyncio.gather(*workers)

        report = Report()
        for scenario in scheduler.discovered:
            result = aggregated.get(scenario.unique_id)
            if result is not None:
                report.add_result(result)
        return report

    async def _run_sequentially(self, scheduler: ScenarioScheduler, **kwargs: Any) -> Report:
        runner = MonotonicScenarioRunner(
            dispatcher=self._dispatcher,
            interrupt_exceptions=(KeyboardInterrupt, SystemExit),
        )
        return await runner.run(scheduler, **kwargs)

    async def _run_worker(
        self,
        assignment: WorkerAssignment,
        workers_total: int,
        scenario_paths: list[str],
        scenarios: dict[str, VirtualScenario],
        aggregated: dict[str, AggregatedResult],
        fire_lock: asyncio.Lock,
    ) -> None:
        env = os.environ.copy()
        env[WORKER_ID_ENV] = str(assignment.worker_id)
        env[WORKERS_TOTAL_ENV] = str(workers_total)
        env[WORKER_GROUPS_ENV] = ','.join(assignment.groups)
        env[NAMESPACE_MAP_ENV] = json.dumps(assignment.namespace_map)
        if assignment.replica_index is not None:
            env[WORKER_REPLICA_INDEX_ENV] = str(assignment.replica_index)
        if assignment.replicas_total is not None:
            env[ENV_REPLICAS_TOTAL_ENV] = str(assignment.replicas_total)

        command = [sys.executable, '-m', 'vedro', 'run', *scenario_paths, '--reporters', 'json']
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        stderr_task = asyncio.create_task(process.stderr.read())
        results: dict[str, ScenarioResult] = {}

        while True:
            line = await process.stdout.readline()
            if not line:
                break
            await self._consume_line(
                line.decode('utf-8', errors='replace'),
                scenarios=scenarios,
                results=results,
                aggregated=aggregated,
                fire_lock=fire_lock,
            )

        await process.wait()
        await stderr_task

    async def _consume_line(
        self,
        line: str,
        scenarios: dict[str, VirtualScenario],
        results: dict[str, ScenarioResult],
        aggregated: dict[str, AggregatedResult],
        fire_lock: asyncio.Lock,
    ) -> None:
        line = line.strip()
        if not line:
            return
        try:
            event = json.loads(line)
        except (TypeError, ValueError):
            return
        if not isinstance(event, dict) or 'event' not in event:
            return

        scenario_id = (event.get('scenario') or {}).get('id')
        scenario = scenarios.get(scenario_id)
        if scenario is None:
            return

        async with fire_lock:
            await self._emit_event(event, scenario, results, aggregated)

    async def _emit_event(
        self,
        event: dict,
        scenario: VirtualScenario,
        results: dict[str, ScenarioResult],
        aggregated: dict[str, AggregatedResult],
    ) -> None:
        kind = event['event']

        if kind == 'scenario_run':
            result = ScenarioResult(scenario)
            results[scenario.unique_id] = result
            await self._dispatcher.fire(ScenarioRunEvent(result))
            return

        if kind in _TERMINAL_EVENTS:
            event_type, mark = _TERMINAL_EVENTS[kind]
            result = results.get(scenario.unique_id)
            if result is None:
                result = ScenarioResult(scenario)
                results[scenario.unique_id] = result
            getattr(result, mark)()
            self._apply_timing(result, event)
            await self._dispatcher.fire(event_type(result))
            return

        if kind == 'scenario_reported':
            result = AggregatedResult(scenario)
            mark = _STATUS_MARKS.get((event.get('scenario') or {}).get('status'))
            if mark is not None:
                getattr(result, mark)()
            self._apply_timing(result, event)
            aggregated[scenario.unique_id] = result
            await self._dispatcher.fire(ScenarioReportedEvent(result))

    @staticmethod
    def _apply_timing(result: ScenarioResult, event: dict) -> None:
        elapsed_ms = (event.get('scenario') or {}).get('elapsed') or 0
        ended_at = time()
        started_at = ended_at - (elapsed_ms / 1000)
        result.set_started_at(started_at)
        result.set_ended_at(ended_at)


__all__ = ("ParallelScenarioRunner",)
