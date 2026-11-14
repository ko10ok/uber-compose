from contexts.compose_file import compose_file
from contexts.isolated_project import isolated_constants
from contexts.isolated_project import isolated_project
from contexts.no_docker_containers import no_docker_containers
from contexts.no_docker_containers import retrieve_all_docker_containers
from d42 import schema
from schemas.docker import ContainerSchema
import vedro

from uber_compose import Environment
from uber_compose import Service
from uber_compose.uber_compose import UberCompose


class Scenario(vedro.Scenario):
    subject = 'up env with subset of multiple auto scanned compose files'

    async def given_no_docker_containers(self):
        no_docker_containers()

    async def given_isolated_project(self):
        self.project = isolated_project()
        self.constants = isolated_constants(self.project)

    async def given_multiple_auto_scanned_compose_files(self):
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
        compose_file(
            'docker-compose.extra.yaml',
            content="""
version: "3"

services:
  mirror:
    image: busybox:stable
    command: 'sh -c "trap : TERM INT; sleep 604800; wait"'
"""
        )

    async def given_env_with_subset_of_services(self):
        self.environment = Environment(
            Service('s1'),
            description='env-a',
        )

    async def when_user_up_env_without_compose_files(self):
        self.response = await UberCompose(
            cfg_constants=self.constants,
        ).up(
            config_template=self.environment,
        )

    async def then_only_services_from_env_should_be_started(self):
        assert retrieve_all_docker_containers() == schema.list([
            ContainerSchema % {
                'Labels': {
                    'com.docker.compose.service': 's1',
                },
            },
        ])
