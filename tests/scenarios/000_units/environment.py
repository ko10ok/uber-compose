
import vedro

from uber_compose import Environment
from uber_compose import Service
from uber_compose.helpers.bytes_pickle import base64_pickled
from uber_compose.helpers.bytes_pickle import debase64_pickled


class Scenario(vedro.Scenario):
    async def given_env(self):
        self.environment = Environment(
            Service('s1'),
            Service('s2'),
        )
        self.packed = base64_pickled(self.environment)

    async def when(self):
        self.unpacked = debase64_pickled(self.packed)

    async def then(self):
        assert isinstance(self.unpacked, Environment)
        assert self.unpacked == self.environment
