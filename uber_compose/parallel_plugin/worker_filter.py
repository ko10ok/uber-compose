from typing import Callable

from vedro.core import ScenarioScheduler
from vedro.core import VirtualScenario


async def ignore_foreign_scenarios(
    scheduler: ScenarioScheduler,
    worker_groups: list[str] | None,
    grouping_key: Callable[[VirtualScenario], str],
) -> None:
    if worker_groups is None:
        return

    allowed = set(worker_groups)
    async for scenario in scheduler:
        if scenario.is_skipped():
            continue
        if grouping_key(scenario) not in allowed:
            scheduler.ignore(scenario)


__all__ = ("ignore_foreign_scenarios",)
