from contexts.compose_file import compose_file
from contexts.isolated_project import isolated_constants
from contexts.isolated_project import isolated_project
from contexts.no_docker_containers import no_docker_containers
from contexts.no_docker_containers import retrieve_all_docker_containers
from contexts.services_started import services_started
from d42 import schema
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
    subject = 'exec singleton preferred over neighbour namespaced service'

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

    async def given_singleton_env_namespaced_neighbour_and_singleton_replica(self):
        self.singleton_environment_a = Environment(
            singleton(Service('db', Env({'MARKER': 'singleton'}))),
            Service('app'),
            description='env-a',
        )
        self.namespaced_environment = Environment(
            Service('db', Env({'MARKER': 'namespaced'})),
            Service('app'),
            description='env-c',
        )
        self.singleton_environment_b = Environment(
            singleton(Service('db', Env({'MARKER': 'singleton'}))),
            Service('app'),
            description='env-b',
        )
        self.response_a = await services_started(
            constants=self.constants,
            compose_files=self.compose_files,
            config_template=self.singleton_environment_a,
            parallelism_limit=2,
            env_id='w0-a',
        )
        self.response_c = await services_started(
            constants=self.constants,
            compose_files=self.compose_files,
            config_template=self.namespaced_environment,
            parallelism_limit=2,
            env_id='w0-c',
        )
        self.response_b = await services_started(
            constants=self.constants,
            compose_files=self.compose_files,
            config_template=self.singleton_environment_b,
            parallelism_limit=2,
            env_id='w0-b',
        )
        self.singleton_container_id = next(
            container['Id']
            for container in retrieve_all_docker_containers()
            if container['Labels'].get('com.docker.compose.service') == 'db'
        )

    async def when_user_execs_singleton_env_without_env_id(self):
        set_current_env_id(self.response_b.env_id)
        self.result = await UberCompose(cfg_constants=self.constants).exec(
            container='db',
            command='echo $MARKER',
        )

    async def then_exec_should_reach_singleton_instead_of_neighbour_namespaced_service(self):
        assert isinstance(self.result, ExecResult)
        assert self.result.stdout == schema.bytes(b'singleton\n')

    async def then_singleton_and_neighbour_namespaced_service_should_stay_running(self):
        assert retrieve_all_docker_containers() == schema.list.len(5)
        assert retrieve_all_docker_containers() == schema.list([
            ...,
            ContainerSchema % {
                'Id': self.singleton_container_id,
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
                    'com.docker.compose.service': f'db-{self.response_c.env_id}',
                    Label.ENV_ID: self.response_c.env_id,
                },
            },
            ...,
        ])
