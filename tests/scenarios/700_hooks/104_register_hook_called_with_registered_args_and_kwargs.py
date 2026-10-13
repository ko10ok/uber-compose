import vedro
from d42 import schema

from contexts.compose_file import compose_file
from contexts.no_docker_compose_files import no_docker_compose_files
from contexts.no_docker_containers import no_docker_containers
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

    async def given_registered_hook_with_args_and_kwargs(self):
        self.calls = []

        def hook(*args, **kwargs):
            self.calls.append((args, kwargs))

        self.uber_compose.on(UberComposeEvent.AFTER_UP, hook, 'positional', keyword='value')

    async def when_user_up_env(self):
        self.response = await self.uber_compose.up(
            compose_files='docker-compose.yaml',
            config_template=Environment(Service('s1')),
        )

    async def then_it_should_return_successful_code(self):
        assert self.response.env_id == schema.str

    async def then_it_should_call_the_hook_with_registered_args_and_kwargs(self):
        assert self.calls == [(('positional',), {'keyword': 'value'})]
