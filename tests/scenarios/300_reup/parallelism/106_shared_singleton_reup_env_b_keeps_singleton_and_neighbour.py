from contexts.compose_file import compose_file
from contexts.isolated_project import isolated_constants
from contexts.isolated_project import isolated_project
from contexts.no_docker_containers import no_docker_containers
from contexts.no_docker_containers import retrieve_all_docker_containers
from contexts.services_started import services_started
from d42 import schema
from helpers.docker_container import get_container_by_service
from helpers.docker_container import get_env_snapshot
from schemas.docker import ContainerSchema
import vedro

from uber_compose import Env
from uber_compose import Environment
from uber_compose import Service
from uber_compose.env_description.env_tools import singleton
from uber_compose.helpers.labels import Label


class Scenario(vedro.Scenario):
    subject = 'reup env b with changed app keeps shared singleton and neighbour env'

    async def given_no_docker_containers(self):
        no_docker_containers()

    async def given_isolated_project(self):
        self.project = isolated_project()
        self.constants = isolated_constants(self.project)

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

    async def given_env_a_and_env_b_are_up(self):
        self.environment_a = Environment(singleton(Service('db')), Service('app'), description='env-a')
        self.environment_b = Environment(singleton(Service('db')), Service('app'), description='env-b')
        self.env_id_a = 'w0-a'
        self.env_id_b = 'w0-b'

        self.response_a = await services_started(
            constants=self.constants,
            compose_files=self.compose_files,
            config_template=self.environment_a,
            parallelism_limit=2,
            env_id=self.env_id_a,
        )
        self.response_b = await services_started(
            constants=self.constants,
            compose_files=self.compose_files,
            config_template=self.environment_b,
            parallelism_limit=2,
            env_id=self.env_id_b,
        )
        self.snapshot_a = get_env_snapshot(self.env_id_a)
        self.db_container_id = get_container_by_service('db')['Id']

    async def when_user_reups_env_b_with_changed_app(self):
        self.changed_environment_b = Environment(
            singleton(Service('db')),
            Service('app', Env({'MARKER': 'new'})),
            description='env-b',
        )
        self.response_b_changed = await services_started(
            constants=self.constants,
            compose_files=self.compose_files,
            config_template=self.changed_environment_b,
            parallelism_limit=2,
            env_id=self.env_id_b,
        )

    async def then_collect_all_containers(self):
        self.containers = retrieve_all_docker_containers()

    async def then_shared_singleton_should_not_be_restarted(self):
        assert get_container_by_service('db', containers=self.containers)['Id'] == self.db_container_id

    async def then_env_a_should_be_untouched(self):
        for container_id, container_state in self.snapshot_a.items():
            assert self.containers == schema.list([
                ...,
                ContainerSchema % {
                    'Id': container_id,
                    'State': container_state['State'],
                    'Labels': {
                        'com.docker.compose.service': container_state['Service'],
                        Label.ENV_ID: self.env_id_a,
                    },
                },
                ...,
            ])
