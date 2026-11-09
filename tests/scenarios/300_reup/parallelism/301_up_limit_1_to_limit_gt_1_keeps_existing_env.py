from contexts.compose_file import compose_file
from contexts.isolated_project import isolated_constants
from contexts.isolated_project import isolated_project
from contexts.no_docker_containers import no_docker_containers
from contexts.no_docker_containers import retrieve_all_docker_containers
from contexts.services_started import services_started
from d42 import schema
from helpers.docker_container import get_env_snapshot
from schemas.docker import ContainerSchema
import vedro

from uber_compose import DEFAULT_ENV_ID
from uber_compose import Environment
from uber_compose import Service
from uber_compose.helpers.labels import Label


class Scenario(vedro.Scenario):
    subject = 'up from limit 1 to limit greater than 1 keeps existing env'

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

    async def given_environment_is_up_with_limit_1(self):
        self.environment = Environment(Service('s1'), description='env-a')
        self.first_response = await services_started(
            constants=self.constants,
            compose_files=self.compose_files,
            config_template=self.environment,
            parallelism_limit=1,
        )
        self.snapshot_default_env = get_env_snapshot(DEFAULT_ENV_ID)

    async def when_user_up_same_environment_with_limit_greater_than_1(self):
        self.second_response = await services_started(
            constants=self.constants,
            compose_files=self.compose_files,
            config_template=self.environment,
            parallelism_limit=2,
        )

    async def then_collect_all_containers(self):
        self.containers = retrieve_all_docker_containers()

    async def then_default_env_should_be_kept(self):
        assert self.first_response.env_id == DEFAULT_ENV_ID
        for container_id, container_state in self.snapshot_default_env.items():
            assert self.containers == schema.list([
                ...,
                ContainerSchema % {
                    'Id': container_id,
                    'State': container_state['State'],
                    'Labels': {
                        'com.docker.compose.service': container_state['Service'],
                        Label.ENV_ID: DEFAULT_ENV_ID,
                    },
                },
                ...,
            ])

    async def then_existing_env_should_be_reused(self):
        assert self.second_response.env_id == DEFAULT_ENV_ID
        containers = self.containers
        assert len(containers) == 1
        assert containers[0]['Labels'].get(Label.ENV_ID) == DEFAULT_ENV_ID
