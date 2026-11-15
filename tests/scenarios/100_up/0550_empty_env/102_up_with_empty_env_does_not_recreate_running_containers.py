from contexts.compose_file import compose_file
from contexts.isolated_project import isolated_constants
from contexts.isolated_project import isolated_project
from contexts.no_docker_containers import no_docker_containers
from contexts.no_docker_containers import retrieve_all_docker_containers
from d42 import schema
from helpers.docker_container import get_container_by_service
from schemas.docker import ContainerSchema
import vedro

from uber_compose import Environment
from uber_compose.uber_compose import UberCompose


class Scenario(vedro.Scenario):
    subject = 'up with empty environment does not recreate running containers'

    async def given_no_docker_containers(self):
        no_docker_containers()

    async def given_isolated_project(self):
        self.project = isolated_project()
        self.constants = isolated_constants(self.project)

    async def given_compose_file_with_services(self):
        compose_file(
            'docker-compose.yaml',
            content="""
version: "3"

services:
  s1:
    image: busybox:stable
    command: 'sh -c "trap : TERM INT; sleep 604800; wait"'

  s2:
    image: busybox:stable
    command: 'sh -c "trap : TERM INT; sleep 604800; wait"'
""",
        )

    async def given_default_environment_is_up(self):
        await UberCompose(
            cfg_constants=self.constants,
        ).up()
        containers_before = retrieve_all_docker_containers()
        self.s1_before = get_container_by_service('s1', containers=containers_before)
        self.s2_before = get_container_by_service('s2', containers=containers_before)

    async def when_user_up_env_with_empty_environment(self):
        self.response = await UberCompose(
            cfg_constants=self.constants,
        ).up(
            config_template=Environment(),
        )

    async def then_only_the_same_two_containers_should_be_running(self):
        self.containers_after = retrieve_all_docker_containers()
        assert self.containers_after == schema.list.len(2)
        assert self.containers_after == schema.list([
            ...,
            ContainerSchema % {
                'Id': self.s1_before['Id'],
                'State': self.s1_before['State'],
                'Labels': {
                    'com.docker.compose.service': 's1',
                },
            },
            ...,
        ])
        assert self.containers_after == schema.list([
            ...,
            ContainerSchema % {
                'Id': self.s2_before['Id'],
                'State': self.s2_before['State'],
                'Labels': {
                    'com.docker.compose.service': 's2',
                },
            },
            ...,
        ])
