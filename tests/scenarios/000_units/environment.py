from uuid import uuid4

import vedro
from d42 import fake
from d42 import schema

from contexts.compose_file import compose_file
from contexts.no_docker_compose_files import no_docker_compose_files
from contexts.no_docker_containers import no_docker_containers
from contexts.no_docker_containers import retrieve_all_docker_containers
from contexts.services_started import services_started
from schemas.docker import ContainerSchema
from schemas.env_name import EnvNameSchema
from uber_compose import Environment
from uber_compose import Service
from uber_compose.helpers.bytes_pickle import base64_pickled
from uber_compose.helpers.bytes_pickle import debase64_pickled
from uber_compose.uber_compose import UberCompose
from uber_compose.env_description.env_types import Env
from uber_compose.helpers.labels import Label
from uber_compose.output.console import LogPolicy


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
