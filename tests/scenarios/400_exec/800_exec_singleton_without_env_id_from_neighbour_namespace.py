from contexts.compose_file import compose_file
from contexts.isolated_project import isolated_constants
from contexts.isolated_project import isolated_project
from contexts.no_docker_containers import no_docker_containers
from contexts.no_docker_containers import retrieve_all_docker_containers
from contexts.services_started import services_started
from d42 import schema
from helpers.docker_container import get_container_by_service
from schemas.docker import ContainerSchema
import vedro

from uber_compose import Env
from uber_compose import Environment
from uber_compose import Service
from uber_compose.env_description.env_tools import singleton
from uber_compose.helpers.current_env import reset_current_env_id
from uber_compose.helpers.current_env import set_current_env_id
from uber_compose.helpers.exec_result import ExecResult
from uber_compose.helpers.labels import Label
from uber_compose.uber_compose import UberCompose


class Scenario(vedro.Scenario):
    subject = 'exec singleton without env id from neighbour namespace'

    async def given_no_docker_containers(self):
        no_docker_containers()

    async def given_isolated_project(self):
        self.project = isolated_project()
        self.constants = isolated_constants(self.project)

    async def given_current_env_reset_for_this_scenario(self):
        vedro.defer(reset_current_env_id)
        reset_current_env_id()

    async def given_compose_files(self):
        self.compose_files = 'docker-compose.yaml'
        compose_file(
            self.compose_files,
            content="""
version: "3"

services:
  db:
    image: busybox:stable
    command: 'sh -c "trap : TERM INT; sleep 604800; wait"'

  app:
    image: busybox:stable
    command: 'sh -c "trap : TERM INT; sleep 604800; wait"'
"""
        )

    async def given_two_envs_with_shared_singleton(self):
        self.environment = Environment(
            singleton(Service('db', Env({'MARKER': 'singleton'}))),
            Service('app'),
            description='env-a',
        )
        self.response_a = await services_started(
            constants=self.constants,
            compose_files=self.compose_files,
            config_template=self.environment,
            parallelism_limit=2,
            env_id='w0-a',
        )
        self.response_b = await services_started(
            constants=self.constants,
            compose_files=self.compose_files,
            config_template=self.environment,
            parallelism_limit=2,
            env_id='w0-b',
        )
        self.db_container_id = get_container_by_service('db')['Id']

    async def when_user_execs_singleton_from_env_b_without_env_id(self):
        set_current_env_id(self.response_b.env_id)
        self.result = await UberCompose(cfg_constants=self.constants).exec(
            container='db',
            command='echo $MARKER',
        )

    async def then_exec_should_reach_shared_singleton(self):
        assert isinstance(self.result, ExecResult)
        assert self.result.stdout == schema.bytes(b'singleton\n')

    async def then_all_containers_should_stay_running(self):
        assert retrieve_all_docker_containers() == schema.list.len(3)
        assert retrieve_all_docker_containers() == schema.list([
            ...,
            ContainerSchema % {
                'Id': self.db_container_id,
                'State': 'running',
                'Labels': {
                    'com.docker.compose.service': 'db',
                    Label.ENV_ID: self.response_a.env_id,
                },
            },
            ...,
        ])
        assert retrieve_all_docker_containers() == schema.list([
            ...,
            ContainerSchema % {
                'State': 'running',
                'Labels': {
                    'com.docker.compose.service': f'app-{self.response_a.env_id}',
                    Label.ENV_ID: self.response_a.env_id,
                },
            },
            ...,
        ])
        assert retrieve_all_docker_containers() == schema.list([
            ...,
            ContainerSchema % {
                'State': 'running',
                'Labels': {
                    'com.docker.compose.service': f'app-{self.response_b.env_id}',
                    Label.ENV_ID: self.response_b.env_id,
                },
            },
            ...,
        ])
