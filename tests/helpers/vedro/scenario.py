from pathlib import Path
from time import monotonic_ns

from vedro import Scenario
from vedro.core import VirtualScenario

from uber_compose import Environment


def make_scenario(env: Environment = None) -> VirtualScenario:
    class _Scenario(Scenario):
        __file__ = Path(f"scenario_{monotonic_ns()}.py").absolute()

    if env:
        _Scenario.env = env
    return VirtualScenario(_Scenario, steps=[])


def describe_scenario(scenario: VirtualScenario) -> dict:
    env = getattr(scenario._orig_scenario, 'env', None)
    env_desc = env.description if env else None

    desc = f"Scenario(name={scenario._orig_scenario.__name__}"
    if hasattr(scenario._orig_scenario, 'env'):
        desc += f", env={scenario._orig_scenario.env}"
    desc += ")"
    return {
        "name": scenario._orig_scenario.__name__,
        "env": env,
        "env_desc": env_desc,
        "description": repr(scenario),
    }
