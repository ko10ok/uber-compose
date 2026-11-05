import asyncio
import base64
import builtins
import json
import os
from pathlib import Path
import sys
from time import time
from typing import Any
from typing import Callable

from vedro.core import AggregatedResult
from vedro.core import Dispatcher
from vedro.core import ExcInfo
from vedro.core import FileArtifact
from vedro.core import MemoryArtifact
from vedro.core import MonotonicScenarioRunner
from vedro.core import Report
from vedro.core import ScenarioResult
from vedro.core import ScenarioRunner
from vedro.core import ScenarioScheduler
from vedro.core import StepResult
from vedro.core import VirtualScenario
from vedro.core import VirtualStep
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


class _RestoredStream:
    def __init__(self, value: str) -> None:
        self._value = value

    def get_value(self) -> str:
        return self._value


class _RestoredCapturedOutput:
    def __init__(self, data: dict | None) -> None:
        data = data or {}
        self.stdout = _RestoredStream(data.get('stdout') or '')
        self.stderr = _RestoredStream(data.get('stderr') or '')


class ParallelScenarioRunner(ScenarioRunner):
    def __init__(
        self,
        dispatcher: Dispatcher,
        grouping_key: Callable[[VirtualScenario], str],
        capture_output: bool = False,
        capture_limit: int | None = None,
        worker_timeout: float | None = None,
    ) -> None:
        self._dispatcher = dispatcher
        self._grouping_key = grouping_key
        self._capture_output = capture_output
        self._capture_limit = capture_limit
        self._worker_timeout = worker_timeout
        self._processes: set = set()

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

        async def run_assignment(assignment: WorkerAssignment):
            return await self._run_worker(
                assignment=assignment,
                workers_total=plan.workers_total,
                scenario_paths=scenario_paths,
                scenarios=scenarios,
                aggregated=aggregated,
                fire_lock=fire_lock,
            )

        workers = [run_assignment(assignment) for assignment in plan.assignments if assignment.groups]
        try:
            worker_runs = await asyncio.gather(*workers)
        except asyncio.CancelledError:
            await self._kill_workers()
            raise
        await self._report_missing_scenarios(scheduler, scenarios, aggregated, worker_runs, fire_lock)

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
    ) -> dict:
        env = os.environ.copy()
        env[WORKER_ID_ENV] = str(assignment.worker_id)
        env[WORKERS_TOTAL_ENV] = str(workers_total)
        env[WORKER_GROUPS_ENV] = ','.join(assignment.groups)
        env[NAMESPACE_MAP_ENV] = json.dumps(assignment.namespace_map)
        if assignment.replica_index is not None:
            env[WORKER_REPLICA_INDEX_ENV] = str(assignment.replica_index)
        if assignment.replicas_total is not None:
            env[ENV_REPLICAS_TOTAL_ENV] = str(assignment.replicas_total)

        command = [sys.executable, '-m', 'vedro', 'run', *scenario_paths, '--reporters', 'json', '-C']
        if self._capture_limit is not None:
            command += ['--capture-limit', str(self._capture_limit)]

        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
        except OSError as exc:
            return {
                'worker_id': assignment.worker_id,
                'returncode': None,
                'stderr': '',
                'spawn_error': str(exc),
                'timeout': False,
            }

        self._processes.add(process)
        stderr_task = asyncio.create_task(process.stderr.read())
        results: dict[str, ScenarioResult] = {}
        buffers: dict[str, list] = {}
        details: dict[str, dict] = {}
        timed_out = False

        try:
            if self._worker_timeout:
                try:
                    stderr_bytes = await asyncio.wait_for(
                        self._stream_process(
                            process, stderr_task, scenarios, results,
                            aggregated, buffers, details, fire_lock,
                        ),
                        timeout=self._worker_timeout,
                    )
                except asyncio.TimeoutError:
                    timed_out = True
                    process.kill()
                    await process.wait()
                    stderr_bytes = await stderr_task
            else:
                stderr_bytes = await self._stream_process(
                    process, stderr_task, scenarios, results,
                    aggregated, buffers, details, fire_lock,
                )
        finally:
            self._processes.discard(process)
            if process.returncode is None:
                try:
                    process.kill()
                    await process.wait()
                except (ProcessLookupError, RuntimeError):
                    pass

        return {
            'worker_id': assignment.worker_id,
            'returncode': process.returncode,
            'stderr': stderr_bytes.decode('utf-8', errors='replace'),
            'spawn_error': None,
            'timeout': timed_out,
        }

    async def _stream_process(
        self,
        process,
        stderr_task,
        scenarios: dict[str, VirtualScenario],
        results: dict[str, ScenarioResult],
        aggregated: dict[str, AggregatedResult],
        buffers: dict[str, list],
        details: dict[str, dict],
        fire_lock: asyncio.Lock,
    ) -> bytes:
        while True:
            line = await process.stdout.readline()
            if not line:
                break
            await self._consume_line(
                line.decode('utf-8', errors='replace'),
                scenarios=scenarios,
                results=results,
                aggregated=aggregated,
                buffers=buffers,
                details=details,
                fire_lock=fire_lock,
            )

        await process.wait()
        stderr_bytes = await stderr_task

        for scenario_id in list(buffers):
            await self._flush_block(scenario_id, buffers, fire_lock)

        return stderr_bytes

    async def _kill_workers(self) -> None:
        for process in list(self._processes):
            if process.returncode is None:
                try:
                    process.kill()
                except ProcessLookupError:
                    pass
        for process in list(self._processes):
            try:
                await process.wait()
            except (ProcessLookupError, RuntimeError):
                pass
        self._processes.clear()

    async def _report_missing_scenarios(
        self,
        scheduler: ScenarioScheduler,
        scenarios: dict[str, VirtualScenario],
        aggregated: dict[str, AggregatedResult],
        worker_runs: list[dict],
        fire_lock: asyncio.Lock,
    ) -> None:
        missing = {}
        for scenario in scheduler.scheduled:
            if scenario.is_skipped():
                continue
            if scenario.unique_id in aggregated:
                continue
            if scenario.unique_id not in scenarios:
                continue
            missing[scenario.unique_id] = scenario

        if not missing:
            return

        message = self._worker_failure_message(worker_runs)
        for scenario in missing.values():
            result = self._build_worker_failure_result(scenario, message)
            aggregated[scenario.unique_id] = AggregatedResult.from_existing(result, [result])
            async with fire_lock:
                await self._dispatcher.fire(ScenarioRunEvent(result))
                await self._dispatcher.fire(ScenarioFailedEvent(result))
                await self._dispatcher.fire(ScenarioReportedEvent(aggregated[scenario.unique_id]))

    def _build_worker_failure_result(self, scenario: VirtualScenario, message: str) -> ScenarioResult:
        result = ScenarioResult(scenario)
        result.mark_failed()
        self._apply_timing(result, {'scenario': {'elapsed': 0}})
        result.add_extra_details(message)

        step_result = StepResult(VirtualStep(self._make_step_callable('parallel worker')))
        step_result.mark_failed()
        step_result.set_exc_info(self._build_exc_info({
            'type': 'RuntimeError',
            'message': message,
        }))
        result.add_step_result(step_result)
        return result

    @staticmethod
    def _worker_failure_message(worker_runs: list[dict]) -> str:
        messages = []
        for run in worker_runs:
            if run.get('spawn_error'):
                messages.append(
                    f"Worker {run['worker_id']} failed to start: {run['spawn_error']}"
                )
            elif run.get('timeout'):
                messages.append(f"Worker {run['worker_id']} timed out")
            elif run.get('returncode') not in (0, None):
                stderr_tail = (run.get('stderr') or '').strip().splitlines()[-5:]
                tail = ' | '.join(stderr_tail)
                messages.append(
                    f"Worker {run['worker_id']} exited with code {run['returncode']}"
                    + (f": {tail}" if tail else '')
                )
        if not messages:
            return 'Parallel worker did not report the scenario result'
        return '; '.join(messages)

    async def _consume_line(
        self,
        line: str,
        scenarios: dict[str, VirtualScenario],
        results: dict[str, ScenarioResult],
        aggregated: dict[str, AggregatedResult],
        buffers: dict[str, list],
        details: dict[str, dict],
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

        kind = event['event']
        if kind == 'uc_scenario_details':
            details[scenario.unique_id] = event
            return

        events = self._build_events(kind, event, scenario, results, aggregated, details)
        if not events:
            return

        buffers.setdefault(scenario.unique_id, []).extend(events)
        if kind == 'scenario_reported':
            await self._flush_block(scenario.unique_id, buffers, fire_lock)

    async def _flush_block(
        self,
        scenario_id: str,
        buffers: dict[str, list],
        fire_lock: asyncio.Lock,
    ) -> None:
        block = buffers.pop(scenario_id, [])
        if not block:
            return
        async with fire_lock:
            for event in block:
                await self._dispatcher.fire(event)

    def _build_events(
        self,
        kind: str,
        event: dict,
        scenario: VirtualScenario,
        results: dict[str, ScenarioResult],
        aggregated: dict[str, AggregatedResult],
        details: dict[str, dict],
    ) -> list:
        if kind == 'scenario_run':
            result = ScenarioResult(scenario)
            results[scenario.unique_id] = result
            return [ScenarioRunEvent(result)]

        if kind in _TERMINAL_EVENTS:
            event_type, mark = _TERMINAL_EVENTS[kind]
            result = results.get(scenario.unique_id)
            if result is None:
                result = ScenarioResult(scenario)
                results[scenario.unique_id] = result
            self._safe_mark(result, mark)
            self._apply_timing(result, event)
            return [event_type(result)]

        if kind == 'scenario_reported':
            scenario_result = results.get(scenario.unique_id)
            if scenario_result is None:
                scenario_result = ScenarioResult(scenario)
                results[scenario.unique_id] = scenario_result
            mark = _STATUS_MARKS.get((event.get('scenario') or {}).get('status'))
            if mark is not None:
                self._safe_mark(scenario_result, mark)
            self._apply_timing(scenario_result, event)
            self._apply_details(scenario_result, event, details.get(scenario.unique_id))
            result = AggregatedResult.from_existing(scenario_result, [scenario_result])
            aggregated[scenario.unique_id] = result
            return [ScenarioReportedEvent(result)]

        return []

    def _apply_details(self, result: AggregatedResult, event: dict, details: dict | None) -> None:
        step_details = (details or {}).get('steps') or []
        for index, step_data in enumerate(event.get('steps') or []):
            step_result = self._build_step_result(step_data, step_details, index)
            result.add_step_result(step_result)

        if details is None:
            return

        for artifact in self._build_artifacts(details.get('artifacts')):
            result.attach(artifact)
        captured_output = details.get('captured_output')
        if captured_output is not None:
            result.set_captured_output(_RestoredCapturedOutput(captured_output))
        for extra in details.get('extra_details') or []:
            result.add_extra_details(extra)

    def _build_step_result(self, step_data: dict, step_details: list, index: int) -> StepResult:
        step_result = StepResult(VirtualStep(self._make_step_callable(step_data.get('name') or '')))
        status = step_data.get('status')
        if status == 'PASSED':
            step_result.mark_passed()
        elif status == 'FAILED':
            step_result.mark_failed()
        self._apply_elapsed(step_result, step_data)
        error = step_data.get('error')
        if error:
            step_result.set_exc_info(self._build_exc_info(error))

        details = step_details[index] if index < len(step_details) else {}
        for artifact in self._build_artifacts(details.get('artifacts')):
            step_result.attach(artifact)
        captured_output = details.get('captured_output')
        if captured_output is not None:
            step_result.set_captured_output(_RestoredCapturedOutput(captured_output))
        for extra in details.get('extra_details') or []:
            step_result.add_extra_details(extra)
        return step_result

    @staticmethod
    def _make_step_callable(name: str):
        def step():
            pass

        step.__name__ = name
        return step

    @staticmethod
    def _build_artifacts(serialized: list | None) -> list:
        artifacts = []
        for item in serialized or []:
            if item.get('kind') == 'memory':
                data = base64.b64decode(item.get('data') or '')
                artifacts.append(MemoryArtifact(item.get('name'), item.get('mime'), data))
            elif item.get('kind') == 'file':
                artifacts.append(FileArtifact(item.get('name'), item.get('mime'), Path(item.get('path'))))
        return artifacts

    @staticmethod
    def _build_exc_info(error: dict) -> ExcInfo:
        type_name = error.get('type') or 'Exception'
        exc_type = getattr(builtins, type_name, None)
        if not isinstance(exc_type, type) or not issubclass(exc_type, BaseException):
            exc_type = type(type_name, (Exception,), {})
        exc_value = exc_type(error.get('message') or '')
        try:
            raise exc_value
        except BaseException:
            traceback = sys.exc_info()[2]
        return ExcInfo(exc_type, exc_value, traceback)

    @staticmethod
    def _safe_mark(result, mark: str) -> None:
        try:
            getattr(result, mark)()
        except RuntimeError:
            pass

    @staticmethod
    def _apply_elapsed(result, data: dict) -> None:
        elapsed_ms = data.get('elapsed') or 0
        ended_at = time()
        started_at = ended_at - (elapsed_ms / 1000)
        result.set_started_at(started_at)
        result.set_ended_at(ended_at)

    @staticmethod
    def _apply_timing(result: ScenarioResult, event: dict) -> None:
        elapsed_ms = (event.get('scenario') or {}).get('elapsed') or 0
        ended_at = time()
        started_at = ended_at - (elapsed_ms / 1000)
        result.set_started_at(started_at)
        result.set_ended_at(ended_at)


__all__ = ("ParallelScenarioRunner",)
