from helpers.vedro.scenario import make_scenario
import vedro

from uber_compose import DEFAULT_ENV_DESCRIPTION
from uber_compose import Environment
from uber_compose import Service
from uber_compose import env_group_key
from uber_compose import env_group_key_for


class Scenario(vedro.Scenario):
    subject = 'env group key groups scenarios by their environment template'

    async def given_scenarios_with_different_envs(self):
        self.env_a = Environment(Service('s1'), description='env-a')
        self.env_a_same = Environment(Service('s1'), description='env-a')
        self.env_b = Environment(Service('s1'), description='env-b')
        self.default_env = Environment(Service('s1'), description=DEFAULT_ENV_DESCRIPTION)

    async def then_same_env_should_have_the_same_key(self):
        assert env_group_key(make_scenario(env=self.env_a)) == env_group_key(make_scenario(env=self.env_a_same))

    async def and_different_env_should_have_a_different_key(self):
        assert env_group_key(make_scenario(env=self.env_a)) != env_group_key(make_scenario(env=self.env_b))

    async def and_default_env_should_be_normalized_to_none_key(self):
        assert env_group_key(make_scenario(env=self.default_env)) == env_group_key_for(None)
        assert env_group_key(make_scenario()) == env_group_key_for(None)

    async def and_any_key_should_be_a_string(self):
        assert isinstance(env_group_key(make_scenario(env=self.env_a)), str)
