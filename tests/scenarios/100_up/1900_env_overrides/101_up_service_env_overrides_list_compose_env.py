from contexts.compose_file import compose_file
from contexts.isolated_project import isolated_constants
from contexts.isolated_project import isolated_project
from contexts.no_docker_containers import no_docker_containers
from contexts.no_docker_containers import retrieve_dockerish_containers
import vedro

from uber_compose.env_description.env_types import Env
from uber_compose.env_description.env_types import Environment
from uber_compose.env_description.env_types import Service
from uber_compose.uber_compose import UberCompose


class Scenario(vedro.Scenario):
    subject = 'service env overrides matching list-style compose env'

    async def given_no_docker_containers(self):
        no_docker_containers()

    async def given_isolated_project(self):
        self.project = isolated_project()
        self.constants = isolated_constants(self.project)

    async def given_compose_file(self):
        self.compose_filename = 'docker-compose.yaml'
        compose_file(
            self.compose_filename,
            content="""
version: "3"

services:
  s1:
    image: busybox:stable
    command: 'sh -c "trap : TERM INT; sleep 604800; wait"'
    environment:
      - ENV_VAR=from_compose
      - KEEP_VAR=keep
"""
        )

    async def given_service_env_override(self):
        self.service = Service('s1', env=Env({'ENV_VAR': 'from_service'}))

    async def when_user_up_env(self):
        self.response = await UberCompose(cfg_constants=self.constants).up(
            config_template=Environment(self.service),
            compose_files=self.compose_filename,
        )

    async def then_service_env_should_win_over_compose_env(self):
        container = retrieve_dockerish_containers()[0]
        env = dict(
            item.split('=', 1)
            for item in container.attrs['Config']['Env']
        )
        assert env['ENV_VAR'] == 'from_service'

    async def and_unrelated_compose_env_should_be_kept(self):
        container = retrieve_dockerish_containers()[0]
        env = dict(
            item.split('=', 1)
            for item in container.attrs['Config']['Env']
        )
        assert env['KEEP_VAR'] == 'keep'
