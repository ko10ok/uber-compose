from vedro.core import ScenarioScheduler
from vedro.core import VirtualScenario

from uber_compose.env_description.env_types import DEFAULT_ENV_DESCRIPTION
from uber_compose.env_description.env_types import Environment
from uber_compose.helpers.bytes_pickle import base64_pickled


async def extract_scenario_config(scenario: VirtualScenario) -> Environment | None:
    scenario_env = None
    if hasattr(scenario._orig_scenario, 'tags'):
        for tag in scenario._orig_scenario.tags:
            if isinstance(tag, Environment):
                scenario_env = tag
    if hasattr(scenario._orig_scenario, 'env'):
        scenario_env = scenario._orig_scenario.env
    return scenario_env


async def extract_scenarios_configs_set(scenarios: ScenarioScheduler) -> set[Environment]:
    needed_configs = set()
    async for scenario in scenarios:
        if scenario.is_skipped():
            continue
        env_config = await extract_scenario_config(scenario)

        if env_config is None:
            needed_configs.add(None)
            continue

        if env_config.description == DEFAULT_ENV_DESCRIPTION:
            needed_configs.add(None)
        else:
            needed_configs.add(env_config)

    return sorted(needed_configs, key=lambda x: base64_pickled(x))


async def mark_skip_unsuitable(scenarios: ScenarioScheduler, env_desc) -> None:
    async for scenario in scenarios:
        scenario_env = await extract_scenario_config(scenario)

        if scenario_env is None:
            scenario_env = Environment(description=DEFAULT_ENV_DESCRIPTION)

        if env_desc != scenario_env.description:
            scenario.skip()
