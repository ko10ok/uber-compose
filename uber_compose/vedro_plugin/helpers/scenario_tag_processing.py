from typing import Iterator
from typing import List

from uber_compose.helpers.bytes_pickle import base64_pickled
from vedro.core import VirtualScenario

from uber_compose.env_description.env_types import Environment


def extract_scenario_config(scenario: VirtualScenario) -> Environment:
    scenario_env = None
    if hasattr(scenario._orig_scenario, 'tags'):
        for tag in scenario._orig_scenario.tags:
            if isinstance(tag, Environment):
                scenario_env = tag
    if hasattr(scenario._orig_scenario, 'env'):
        scenario_env = scenario._orig_scenario.env
    return scenario_env


def extract_scenarios_configs_set(scenarios: List[VirtualScenario] | Iterator[VirtualScenario]) -> set[Environment]:
    needed_configs = set()
    for scenario in scenarios:
        needed_configs.add(extract_scenario_config(scenario))
    return sorted(needed_configs, key=lambda x: base64_pickled(x))
