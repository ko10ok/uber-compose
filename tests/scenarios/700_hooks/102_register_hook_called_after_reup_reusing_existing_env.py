import vedro
from d42 import schema

from contexts.compose_file import compose_file
from contexts.no_docker_compose_files import no_docker_compose_files
from contexts.no_docker_containers import no_docker_containers
from contexts.services_started import services_started
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
        self.compose_files = 'docker-compose.yaml'
        compose_file(
            self.compose_files,
            content="""
version: "3"

services:
  s1:
    image: busybox:stable
    command: 'sh -c "trap : TERM INT; sleep 604800; wait"'
"""
        )

    async def given_environment(self):
        self.environment = Environment(Service('s1'))

    async def given_already_running_env(self):
        self.started_service = await services_started(
            compose_files=self.compose_files,
            config_template=self.environment,
        )

    async def given_uber_compose_instance(self):
        self.uber_compose = UberCompose()

    async def given_registered_hooks(self):
        self.calls = []
        self.updated_env_up_calls = []
        self.uber_compose.on(UberComposeEvent.AFTER_UP, self.calls.append, 'after_up_called')
        self.uber_compose.on(
            UberComposeEvent.AFTER_UPDATED_ENV_UP, self.updated_env_up_calls.append, 'after_updated_env_up_called'
        )

    async def when_user_up_env_again_without_changes(self):
        self.response = await self.uber_compose.up(
            compose_files=self.compose_files,
            config_template=self.environment,
        )

    async def then_it_should_reuse_existing_env(self):
        assert self.response.env_id == self.started_service.env_id

    async def then_it_should_call_the_registered_hook(self):
        assert self.calls == ['after_up_called']

    async def then_it_should_not_call_the_after_updated_env_up_hook(self):
        assert self.updated_env_up_calls == []
