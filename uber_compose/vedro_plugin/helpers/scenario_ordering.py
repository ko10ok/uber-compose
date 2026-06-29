from typing import List

from vedro.core import ScenarioOrderer
from vedro.core import VirtualScenario

from uber_compose.helpers.bytes_pickle import base64_pickled
from uber_compose.vedro_plugin.helpers.scenario_tag_processing import extract_scenario_config


class EnvTagsOrderer(ScenarioOrderer):
    async def sort(self, scenarios: List[VirtualScenario]) -> List[VirtualScenario]:
        copied = scenarios[:]

        keys = {}
        for scenario in copied:
            config = await extract_scenario_config(scenario)
            keys[id(scenario)] = base64_pickled(config)

        return sorted(
            copied,
            key=lambda x: keys[id(x)]
        )
