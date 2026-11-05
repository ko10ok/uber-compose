from contexts.compose_file import compose_file
from contexts.no_docker_compose_files import no_docker_compose_files
from contexts.no_docker_containers import no_docker_containers
from d42 import schema
import vedro

from uber_compose import Environment
from uber_compose import Service
from uber_compose import UberComposeEvent
from uber_compose.uber_compose import TheUberCompose


def _reset_singleton_state():
    TheUberCompose()._hooks._hooks[UberComposeEvent.AFTER_UP].clear()
    TheUberCompose()._hooks._hooks[UberComposeEvent.AFTER_UPDATED_ENV_UP].clear()
    TheUberCompose()._previous_release_id = None


class Scenario(vedro.Scenario):
    subject = 'up with unrelated new env by the same client fires only AFTER_UP'

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

    async def given_the_singleton_reset_for_this_scenario(self):
        vedro.defer(_reset_singleton_state)
        _reset_singleton_state()

    async def given_registered_hooks_on_the_singleton(self):
        self.after_up_calls = []
        self.after_updated_env_up_calls = []
        TheUberCompose().on(UberComposeEvent.AFTER_UP, self.after_up_calls.append, 'after_up_called')
        TheUberCompose().on(
            UberComposeEvent.AFTER_UPDATED_ENV_UP,
            self.after_updated_env_up_calls.append,
            'after_updated_env_up_called',
        )

    async def given_unrelated_env_a_up_by_the_singleton(self):
        self.environment_a = Environment(Service('s1'), description='env-a')
        self.response_a = await TheUberCompose().up(
            compose_files=self.compose_files,
            config_template=self.environment_a,
        )

    async def when_the_singleton_ups_unrelated_env_b(self):
        self.environment_b = Environment(Service('s2'), description='env-b')
        self.response_b = await TheUberCompose().up(
            compose_files=self.compose_files,
            config_template=self.environment_b,
        )

    async def then_both_envs_should_have_been_up(self):
        assert self.response_a.env_id == schema.str
        assert self.response_b.env_id == schema.str

    async def then_each_up_should_fire_after_up(self):
        assert self.after_up_calls == schema.list([
            schema.str('after_up_called'),
            schema.str('after_up_called'),
        ])

    async def then_env_b_up_should_not_fire_after_updated_env_up(self):
        assert self.after_updated_env_up_calls == schema.list([])
