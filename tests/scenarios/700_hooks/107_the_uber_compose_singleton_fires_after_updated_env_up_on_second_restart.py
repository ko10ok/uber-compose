import vedro
from d42 import schema

from contexts.compose_file import compose_file
from contexts.no_docker_compose_files import no_docker_compose_files
from contexts.no_docker_containers import no_docker_containers
from uber_compose import Environment
from uber_compose import Service
from uber_compose import UberComposeEvent
from uber_compose.env_description.env_types import Env
from uber_compose.uber_compose import TheUberCompose


def _clear_hooks():
    TheUberCompose()._hooks._hooks[UberComposeEvent.AFTER_UP].clear()
    TheUberCompose()._hooks._hooks[UberComposeEvent.AFTER_UPDATED_ENV_UP].clear()
    TheUberCompose()._previous_release_id = None


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

    async def given_the_singleton_reset_for_this_scenario(self):
        vedro.defer(_clear_hooks)
        TheUberCompose()._previous_release_id = None

    async def given_registered_after_updated_env_up_hook_on_the_singleton(self):
        self.calls = []
        TheUberCompose().on(
            UberComposeEvent.AFTER_UPDATED_ENV_UP, self.calls.append, 'after_updated_env_up_called'
        )

    async def given_the_singleton_already_up_once(self):
        await TheUberCompose().up(
            compose_files='docker-compose.yaml',
            config_template=Environment(Service('s1')),
        )

    async def when_the_singleton_ups_again_with_a_changed_environment(self):
        self.response = await TheUberCompose().up(
            compose_files='docker-compose.yaml',
            config_template=Environment(Service('s1', Env({'A': '1'}))),
        )

    async def then_it_should_return_successful_code(self):
        assert self.response.env_id == schema.str

    async def then_it_should_call_the_after_updated_env_up_hook_without_checking_docker_state(self):
        assert self.calls == ['after_updated_env_up_called']
