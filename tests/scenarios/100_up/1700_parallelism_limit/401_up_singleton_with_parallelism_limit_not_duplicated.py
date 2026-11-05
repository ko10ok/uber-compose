from contexts.compose_file import compose_file
from contexts.no_docker_compose_files import no_docker_compose_files
from contexts.no_docker_containers import no_docker_containers
from contexts.no_docker_containers import retrieve_all_docker_containers
from contexts.services_started import services_started
from d42 import schema
from helpers.docker_container import get_container_by_service
from schemas.docker import ContainerSchema
import vedro

from uber_compose import Environment
from uber_compose import Service
from uber_compose.env_description.env_tools import singleton
from uber_compose.helpers.labels import Label


class Scenario(vedro.Scenario):
    subject = 'up with singleton service and parallelism_limit=2 keeps singleton shared and not duplicated'

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
  db:
    image: busybox:stable
    command: 'sh -c "trap : TERM INT; sleep 604800; wait"'

  app:
    image: busybox:stable
    command: 'sh -c "trap : TERM INT; sleep 604800; wait"'
"""
        )

    async def given_env_a_up_with_parallelism_limit(self):
        self.environment_a = Environment(
            singleton(Service('db')),
            Service('app'),
            description='env-a',
        )
        self.response_a = await services_started(
            compose_files=self.compose_files,
            config_template=self.environment_a,
            parallelism_limit=2,
        )
        self.db_container_before_env_b = get_container_by_service('db')
        self.db_container_id_before_env_b = self.db_container_before_env_b['Id']

    async def when_env_b_up_with_parallelism_limit(self):
        self.environment_b = Environment(
            singleton(Service('db')),
            Service('app'),
            description='env-b',
        )
        self.response_b = await services_started(
            compose_files=self.compose_files,
            config_template=self.environment_b,
            parallelism_limit=2,
        )
        self.containers = retrieve_all_docker_containers()

    async def then_both_envs_should_have_distinct_env_ids(self):
        assert self.response_a.env_id == schema.str
        assert self.response_b.env_id == schema.str
        assert self.response_a.env_id != self.response_b.env_id

    async def then_singleton_should_be_up_exactly_once_and_not_restarted(self):
        assert self.containers == schema.list([
            ...,
            ContainerSchema % {
                'Id': self.db_container_id_before_env_b,
                'Labels': {
                    'com.docker.compose.service': 'db',
                    Label.TEMPLATE_SERVICE_NAME: 'db',
                },
            },
            ...,
        ])
        assert len(self.containers) == 3

    async def then_each_namespace_should_have_its_own_app_container(self):
        assert self.containers == schema.list([
            ...,
            ContainerSchema % {
                'Labels': {
                    'com.docker.compose.service': f'app-{self.response_a.env_id}',
                    Label.ENV_ID: self.response_a.env_id,
                },
            },
            ...,
        ])
        assert self.containers == schema.list([
            ...,
            ContainerSchema % {
                'Labels': {
                    'com.docker.compose.service': f'app-{self.response_b.env_id}',
                    Label.ENV_ID: self.response_b.env_id,
                },
            },
            ...,
        ])
