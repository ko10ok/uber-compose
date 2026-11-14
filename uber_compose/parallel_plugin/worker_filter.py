from typing import Callable

from vedro.core import ScenarioScheduler
from vedro.core import VirtualScenario


async def ignore_foreign_scenarios(
    scheduler: ScenarioScheduler,
    worker_groups: list[str] | None,
    grouping_key: Callable[[VirtualScenario], str],
    replica_index: int | None = None,
    replicas_total: int | None = None,
) -> None:
    if worker_groups is None:
        return

    allowed = set(worker_groups)
    scenarios = [scenario async for scenario in scheduler]
    grouped: dict[str, list[VirtualScenario]] = {}

    for scenario in scenarios:
        if scenario.is_skipped():
            continue
        group_key = grouping_key(scenario)
        if group_key not in allowed:
            scheduler.ignore(scenario)
            continue
        grouped.setdefault(group_key, []).append(scenario)

    if replicas_total and replicas_total > 1 and replica_index is not None:
        for group_scenarios in grouped.values():
            ordered = sorted(group_scenarios, key=lambda item: item.unique_id)
            for position, scenario in enumerate(ordered):
                if position % replicas_total != replica_index:
                    scheduler.ignore(scenario)


__all__ = ("ignore_foreign_scenarios",)
