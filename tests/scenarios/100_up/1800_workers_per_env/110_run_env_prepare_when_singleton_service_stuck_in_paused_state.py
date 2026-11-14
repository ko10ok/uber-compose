from contexts.compose_file import compose_file
from contexts.isolated_project import isolated_constants
from contexts.isolated_project import isolated_project
from contexts.no_docker_containers import no_docker_containers
from contexts.no_docker_containers import paused_docker_container
from contexts.no_docker_containers import retrieve_all_docker_containers
from d42 import schema
from schemas.docker import ContainerSchema
import vedro

from uber_compose import Environment
from uber_compose import Service
from uber_compose.core.utils.compose_instance_cfg import get_stable_env_id
from uber_compose.env_description.env_tools import singleton
from uber_compose.helpers.labels import Label
from uber_compose.uber_compose import UberCompose


class Scenario(vedro.Scenario):
    subject = 'run env prepare when singleton service is stuck in paused state'

    async def given_no_docker_containers(self):
        no_docker_containers()

    async def given_isolated_project(self):
        self.project = isolated_project()
        self.constants = isolated_constants(self.project)

    async def given_compose_file(self):
        self.compose_files = 'docker-compose.yaml'
        compose_file(
            self.compose_files,
            content="""
version: "3"

services:
  redis:
    image: busybox:stable
    command: 'sh -c "trap : TERM INT; sleep 604800; wait"'

  app:
    image: busybox:stable
    command: 'sh -c "trap : TERM INT; sleep 604800; wait"'
"""
        )

    async def given_env_with_singleton_and_two_replicas(self):
        self.environment = Environment(
            singleton(Service('redis')),
            Service('app'),
            description='env-a',
        )
        await UberCompose(
            cfg_constants=self.constants,
        ).prepare_parallel_environments(
            config_templates=[self.environment],
            compose_files=self.compose_files,
            workers_per_env={'env-a': 2},
        )
        self.env_ids = [
            get_stable_env_id(self.environment, index)
            for index in range(2)
        ]

    async def given_singleton_is_stuck_in_paused_state(self):
        paused_docker_container('redis')

    async def when_user_prepares_env_with_singleton_service_stuck_in_paused_state(self):
        self.ready_envs = await UberCompose(
            cfg_constants=self.constants,
        ).prepare_parallel_environments(
            config_templates=[self.environment],
            compose_files=self.compose_files,
            workers_per_env={'env-a': 2},
        )

    async def then_singleton_and_all_replicas_should_be_running(self):
        self.containers = retrieve_all_docker_containers()
        assert self.containers == schema.list.len(3)
        assert self.containers == schema.list([
            ...,
            ContainerSchema % {
                'State': 'running',
                'Labels': {
                    'com.docker.compose.service': 'redis',
                    Label.TEMPLATE_SERVICE_NAME: 'redis',
                },
            },
            ...,
        ])
        assert self.containers == schema.list([
            ...,
            ContainerSchema % {
                'State': 'running',
                'Labels': {
                    'com.docker.compose.service': f'app-{self.env_ids[0]}',
                    Label.ENV_ID: self.env_ids[0],
                },
            },
            ...,
        ])
        assert self.containers == schema.list([
            ...,
            ContainerSchema % {
                'State': 'running',
                'Labels': {
                    'com.docker.compose.service': f'app-{self.env_ids[1]}',
                    Label.ENV_ID: self.env_ids[1],
                },
            },
            ...,
        ])
