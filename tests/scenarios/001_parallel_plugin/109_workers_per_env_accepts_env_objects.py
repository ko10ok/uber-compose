import vedro

from uber_compose import Environment
from uber_compose import Service
from uber_compose.parallel_plugin.worker_api import get_workers_per_env
from uber_compose.parallel_plugin.worker_api import reset_workers_per_env
from uber_compose.parallel_plugin.worker_api import set_workers_per_env


class Scenario(vedro.Scenario):
    subject = 'workers per env mapping accepts environment objects as keys'

    async def given_workers_per_env_with_env_object_key(self):
        self.environment = Environment(Service('s1'), description='env-a')
        set_workers_per_env({self.environment: 3}, default=1)
        vedro.defer(reset_workers_per_env)

    async def then_it_should_normalize_key_to_environment_description(self):
        counts, default = get_workers_per_env()
        assert counts == {'env-a': 3}
        assert default == 1
