import vedro
from d42 import schema

from contexts.compose_file import compose_file
from contexts.no_docker_compose_files import no_docker_compose_files
from contexts.no_docker_containers import no_docker_containers
from contexts.no_docker_containers import retrieve_all_docker_containers
from schemas.docker import ContainerSchema
from uber_compose import Environment
from uber_compose import Service
from uber_compose import UberComposeEvent
from uber_compose.env_description.env_types import Env
from uber_compose.helpers.labels import Label
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

  s2:
    image: busybox:stable
    command: 'sh -c "trap : TERM INT; sleep 604800; wait"'
"""
        )

    async def given_uber_compose_instance(self):
        self.uber_compose = UberCompose()

    async def given_already_running_env_started_by_the_same_instance(self):
        self.started_service = await self.uber_compose.up(
            compose_files=self.compose_files,
            config_template=Environment(
                Service('s1'),
                Service('s2'),
            ),
        )
        self.started_containers = retrieve_all_docker_containers()

    async def given_registered_hooks(self):
        self.after_up_calls = []
        self.after_updated_env_up_calls = []
        self.uber_compose.on(UberComposeEvent.AFTER_UP, self.after_up_calls.append, 'after_up_called')
        self.uber_compose.on(
            UberComposeEvent.AFTER_UPDATED_ENV_UP, self.after_updated_env_up_calls.append, 'after_updated_env_up_called'
        )

    async def given_changed_environment(self):
        self.changed_environment = Environment(
            Service('s1', Env({'A': '1'})),
            Service('s2'),
        )

    async def when_user_up_env_again_with_changed_service_env(self):
        self.response = await self.uber_compose.up(
            compose_files=self.compose_files,
            config_template=self.changed_environment,
        )

    async def then_it_should_restart_the_same_env_not_from_scratch(self):
        assert self.response.env_id == self.started_containers[0]['Labels'][Label.ENV_ID]

    async def then_it_should_up_changed_service_with_new_env_var(self):
        self.containers = retrieve_all_docker_containers()
        assert self.containers == schema.list([
            ...,
            ContainerSchema % {
                'Labels': {
                    'com.docker.compose.service': 's1',
                },
            },
            ...,
        ])

    async def then_it_should_call_the_after_up_hook(self):
        assert self.after_up_calls == ['after_up_called']

    async def then_it_should_call_the_after_updated_env_up_hook(self):
        assert self.after_updated_env_up_calls == ['after_updated_env_up_called']

