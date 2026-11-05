from collections import defaultdict
from typing import Callable

from vedro.core import ScenarioScheduler
from vedro.core import VirtualScenario

from uber_compose.parallel_plugin.types import ExecutionPlan
from uber_compose.parallel_plugin.types import WorkerAssignment


async def collect_group_counts(
    scenarios: ScenarioScheduler,
    grouping_key: Callable[[VirtualScenario], str],
) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    async for scenario in scenarios:
        if scenario.is_skipped():
            continue
        counts[grouping_key(scenario)] += 1
    return dict(counts)


def assign_groups_to_workers(group_counts: dict[str, int], workers_total: int) -> list[list[str]]:
    workers_total = max(workers_total, 1)
    workers: list[list[str]] = [[] for _ in range(workers_total)]
    worker_loads = [0] * workers_total

    groups = sorted(group_counts.items(), key=lambda item: (-item[1], item[0]))
    for group_key, count in groups:
        worker_id = min(range(workers_total), key=lambda index: (worker_loads[index], index))
        workers[worker_id].append(group_key)
        worker_loads[worker_id] += count

    return workers


def build_execution_plan(
    group_counts: dict[str, int],
    workers_total: int,
    namespace_map: dict[str, str] | None = None,
) -> ExecutionPlan:
    namespace_map = namespace_map or {}
    workers = assign_groups_to_workers(group_counts, workers_total)
    assignments = tuple(
        WorkerAssignment(
            worker_id=worker_id,
            groups=tuple(sorted(groups)),
            namespace_map={group: namespace_map[group] for group in groups if group in namespace_map},
        )
        for worker_id, groups in enumerate(workers)
    )
    return ExecutionPlan(workers_total=max(workers_total, 1), assignments=assignments)


async def build_execution_plan_from_scheduler(
    scenarios: ScenarioScheduler,
    workers_total: int,
    grouping_key: Callable[[VirtualScenario], str],
    namespace_map: dict[str, str] | None = None,
) -> ExecutionPlan:
    group_counts = await collect_group_counts(scenarios, grouping_key)
    return build_execution_plan(group_counts, workers_total, namespace_map)


__all__ = (
    'assign_groups_to_workers', 'build_execution_plan', 'build_execution_plan_from_scheduler',
    'collect_group_counts',
)
