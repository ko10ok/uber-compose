from contexts.compose_file import compose_file
from contexts.no_docker_compose_files import no_docker_compose_files
from contexts.no_docker_containers import no_docker_containers
from d42 import schema
import vedro

from uber_compose import Environment
from uber_compose import Service
from uber_compose import UberComposeEvent
from uber_compose.uber_compose import UberCompose


class Scenario(vedro.Scenario):
    async def given_no_docker_containers(self):
        no_docker_containers()

    async def given_no_docker_compose_files(self):
        no_docker_compose_files()

    async def given_compose_files(self):
        compose_file(
            'docker-compose.yaml',
            content="""
version: "3"

services:
  s1:
    image: busybox:stable
    command: 'sh -c "trap : TERM INT; sleep 604800; wait"'
"""
        )

    async def given_uber_compose_instance(self):
        self.uber_compose = UberCompose()

    async def given_several_registered_hooks(self):
        self.calls = []

        async def async_hook(marker):
            self.calls.append(marker)

        self.uber_compose.on(UberComposeEvent.AFTER_UP, self.calls.append, 'first_sync')
        self.uber_compose.on(UberComposeEvent.AFTER_UP, async_hook, 'second_async')
        self.uber_compose.on(UberComposeEvent.AFTER_UP, self.calls.append, 'third_sync')

    async def when_user_up_env(self):
        self.response = await self.uber_compose.up(
            compose_files='docker-compose.yaml',
            config_template=Environment(Service('s1')),
        )

    async def then_it_should_return_successful_code(self):
        assert self.response.env_id == schema.str

    async def then_it_should_call_hooks_in_registration_order(self):
        assert self.calls == ['first_sync', 'second_async', 'third_sync']
