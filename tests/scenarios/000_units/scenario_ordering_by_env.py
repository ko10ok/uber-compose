import vedro
from vedro.core import MonotonicScenarioScheduler
from d42 import schema

from helpers.vedro.scenario import make_scenario
from uber_compose.env_description.env_types import DEFAULT_ENV_DESCRIPTION
from uber_compose.env_description.env_types import Environment
from uber_compose.env_description.env_types import Service
from uber_compose.vedro_plugin.helpers.scenario_ordering import EnvTagsOrderer


class Scenario(vedro.Scenario):
    async def given_scenarios_with_mixed_envs(self):
        self.default_env = Environment(Service('s1'), description=DEFAULT_ENV_DESCRIPTION)
        self.another_env = Environment(Service('s2'), description='another')

        self.scenarios = [
            make_scenario(env=self.another_env),
            make_scenario(env=self.default_env),
            make_scenario(env=self.another_env),
        ]

    async def when_orderer_sorts_scenarios(self):
        self.orderer = EnvTagsOrderer()
        self.sorted_scenarios = await self.orderer.sort(self.scenarios)

    async def then_scenarios_should_be_grouped_by_env(self):
        self.sorted_scenarios_descriptions = [
            getattr(s._orig_scenario, 'env', None).description
            for s in self.sorted_scenarios
        ]
        assert self.sorted_scenarios_descriptions == schema.list([
            schema.str(DEFAULT_ENV_DESCRIPTION),
            schema.str('another'),
            schema.str('another'),
        ])
