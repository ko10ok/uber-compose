from contexts.compose_file import compose_file
from contexts.isolated_project import isolated_constants
from contexts.isolated_project import isolated_project
from contexts.no_docker_containers import no_docker_containers
from contexts.no_docker_containers import retrieve_all_docker_containers
from contexts.services_started import services_started
from d42 import schema
from schemas.docker import ContainerSchema
import vedro

from uber_compose import Environment
from uber_compose import Service
from uber_compose.helpers.labels import Label


class Scenario(vedro.Scenario):
    subject = 'up same env id with force restart recreates env'

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
  s1:
    image: busybox:stable
    command: 'sh -c "trap : TERM INT; sleep 604800; wait"'
"""
        )

    async def given_env_already_up_with_explicit_env_id(self):
        self.requested_env_id = 'w0-force'
        self.release_id = 'fixed-release'
        self.environment = Environment(Service('s1'), description='env-a')
        self.first_response = await services_started(
            constants=self.constants,
            compose_files=self.compose_files,
            config_template=self.environment,
            parallelism_limit=2,
            env_id=self.requested_env_id,
            release_id=self.release_id,
        )
        self.first_containers = retrieve_all_docker_containers()

    async def when_user_up_same_env_id_with_force_restart(self):
        self.second_response = await services_started(
            constants=self.constants,
            compose_files=self.compose_files,
            config_template=self.environment,
            parallelism_limit=2,
            env_id=self.requested_env_id,
            release_id=self.release_id,
            force_restart=True,
        )

    async def then_it_should_keep_requested_env_id(self):
        assert self.first_response.env_id == self.requested_env_id
        assert self.second_response.env_id == self.requested_env_id

    async def and_it_should_recreate_containers(self):
        first_ids = {container['Id'] for container in self.first_containers}
        second_containers = retrieve_all_docker_containers()
        second_ids = {container['Id'] for container in second_containers}
        assert first_ids.isdisjoint(second_ids)

        assert second_containers == schema.list([
            ContainerSchema % {
                'Labels': {
                    'com.docker.compose.service': f's1-{self.requested_env_id}',
                    Label.ENV_ID: self.requested_env_id,
                    Label.ENV_DESCRIPTION: str(self.environment),
                },
            },
        ])
