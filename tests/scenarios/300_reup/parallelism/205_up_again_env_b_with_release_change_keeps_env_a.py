from contexts.compose_file import compose_file
from contexts.isolated_project import isolated_constants
from contexts.isolated_project import isolated_project
from contexts.no_docker_containers import no_docker_containers
from contexts.no_docker_containers import retrieve_all_docker_containers
from contexts.services_started import services_started
from d42 import schema
from helpers.docker_container import get_containers_by_env_id
from helpers.docker_container import get_env_snapshot
from schemas.docker import ContainerSchema
import vedro

from uber_compose import Environment
from uber_compose import Service
from uber_compose.helpers.labels import Label


class Scenario(vedro.Scenario):
    subject = 'up again env b with release change only reuses env and keeps env a untouched'

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

  s2:
    image: busybox:stable
    command: 'sh -c "trap : TERM INT; sleep 604800; wait"'
"""
        )

    async def given_env_a_and_env_b_are_up(self):
        self.environment_a = Environment(Service('s1'), Service('s2'), description='env-a')
        self.environment_b = Environment(Service('s1'), Service('s2'), description='env-b')
        self.env_id_a = 'w0-a'
        self.env_id_b = 'w0-b'
        self.start_release = 'start-release'

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
            release_id=self.start_release,
        )
        self.snapshot_a = get_env_snapshot(self.env_id_a)
        self.ids_b_before = {container['Id'] for container in get_containers_by_env_id(self.env_id_b)}

    async def when_user_reups_env_b_with_new_release(self):
        self.response_b_reused = await services_started(
            constants=self.constants,
            compose_files=self.compose_files,
            config_template=self.environment_b,
            parallelism_limit=2,
            env_id=self.env_id_b,
            release_id='next-release',
        )

    async def then_collect_all_containers(self):
        self.containers = retrieve_all_docker_containers()

    async def then_env_b_should_keep_running_release(self):
        containers_b = get_containers_by_env_id(self.env_id_b, self.containers)
        assert {container['Id'] for container in containers_b} == self.ids_b_before
        assert all(
            container['Labels'].get(Label.RELEASE_ID) == self.start_release
            for container in containers_b
        )

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
