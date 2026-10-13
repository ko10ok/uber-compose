import vedro
from d42 import schema

from contexts.compose_file import compose_file
from contexts.no_docker_compose_files import no_docker_compose_files
from contexts.no_docker_containers import no_docker_containers
from uber_compose import Environment
from uber_compose import Service
from uber_compose import UberComposeEvent
from uber_compose.uber_compose import TheUberCompose


def _clear_after_up_hooks():
    TheUberCompose()._hooks._hooks[UberComposeEvent.AFTER_UP].clear()


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

    async def given_registered_hook_on_the_singleton(self):
        vedro.defer(_clear_after_up_hooks)

        self.calls = []
        TheUberCompose().on(UberComposeEvent.AFTER_UP, self.calls.append, 'after_up_called')

    async def when_user_up_env_via_the_singleton(self):
        self.response = await TheUberCompose().up(
            compose_files='docker-compose.yaml',
            config_template=Environment(Service('s1')),
        )

    async def then_it_should_return_successful_code(self):
        assert self.response.env_id == schema.str

    async def then_it_should_call_the_hook_registered_on_the_same_singleton_instance(self):
        assert self.calls == ['after_up_called']
