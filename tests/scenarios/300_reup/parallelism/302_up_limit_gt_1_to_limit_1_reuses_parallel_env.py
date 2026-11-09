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

from uber_compose import Environment
from uber_compose import Service
from uber_compose.helpers.labels import Label


class Scenario(vedro.Scenario):
    subject = 'up from limit greater than 1 to limit 1 reuses one parallel env'

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

    async def given_two_parallel_envs_are_up(self):
        self.environment = Environment(Service('s1'), description='env-a')
        self.env_id_0 = 'w0-a'
        self.env_id_1 = 'w0-b'

        self.response_0 = await services_started(
            constants=self.constants,
            compose_files=self.compose_files,
            config_template=self.environment,
            parallelism_limit=2,
            env_id=self.env_id_0,
        )
        self.response_1 = await services_started(
            constants=self.constants,
            compose_files=self.compose_files,
            config_template=self.environment,
            parallelism_limit=2,
            env_id=self.env_id_1,
        )
        self.snapshot_0 = get_env_snapshot(self.env_id_0)
        self.snapshot_1 = get_env_snapshot(self.env_id_1)

    async def when_user_up_same_environment_with_limit_1(self):
        self.reused_response = await services_started(
            constants=self.constants,
            compose_files=self.compose_files,
            config_template=self.environment,
            parallelism_limit=1,
        )

    async def then_collect_all_containers(self):
        self.containers = retrieve_all_docker_containers()

    async def then_it_should_reuse_one_of_parallel_envs(self):
        assert self.reused_response.env_id in {self.env_id_0, self.env_id_1}

    async def then_both_parallel_envs_should_be_untouched(self):
        for container_id, container_state in self.snapshot_0.items():
            assert self.containers == schema.list([
                ...,
                ContainerSchema % {
                    'Id': container_id,
                    'State': container_state['State'],
                    'Labels': {
                        'com.docker.compose.service': container_state['Service'],
                        Label.ENV_ID: self.env_id_0,
                    },
                },
                ...,
            ])
        for container_id, container_state in self.snapshot_1.items():
            assert self.containers == schema.list([
                ...,
                ContainerSchema % {
                    'Id': container_id,
                    'State': container_state['State'],
                    'Labels': {
                        'com.docker.compose.service': container_state['Service'],
                        Label.ENV_ID: self.env_id_1,
                    },
                },
                ...,
            ])
