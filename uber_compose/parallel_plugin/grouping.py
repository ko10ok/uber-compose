from vedro.core import VirtualScenario

from uber_compose.env_description.env_types import DEFAULT_ENV_DESCRIPTION
from uber_compose.env_description.env_types import Environment
from uber_compose.helpers.bytes_pickle import base64_pickled


def scenario_env(scenario: VirtualScenario) -> Environment | None:
    original = getattr(scenario, '_orig_scenario', scenario)
    env = None
    if hasattr(original, 'tags'):
        for tag in original.tags:
            if isinstance(tag, Environment):
                env = tag
    if hasattr(original, 'env'):
        env = original.env
    return env


def env_group_key_for(env: Environment | None) -> str:
    if env is None or env.description == DEFAULT_ENV_DESCRIPTION:
        env = None
    return base64_pickled(env)


def env_group_key(scenario: VirtualScenario) -> str:
    return env_group_key_for(scenario_env(scenario))


__all__ = ("env_group_key", "env_group_key_for", "scenario_env",)
