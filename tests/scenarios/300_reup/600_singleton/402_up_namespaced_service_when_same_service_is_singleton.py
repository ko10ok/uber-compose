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
from uber_compose import Service
from uber_compose.core.utils.compose_instance_cfg import get_stable_env_id
from uber_compose.env_description.env_tools import singleton
from uber_compose.helpers.labels import Label
from uber_compose.uber_compose import UberCompose


class Scenario(vedro.Scenario):
    subject = 'up namespaced service when same service is already running as singleton'

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
  redis:
    image: busybox:stable
    command: 'sh -c "trap : TERM INT; sleep 604800; wait"'
"""
        )

    async def given_env_with_singleton_redis_is_running(self):
        self.redis = Service('redis')
        self.ready_env = await UberCompose(
            cfg_constants=self.constants,
        ).up(
            compose_files=self.compose_files,
            config_template=Environment(
                singleton(self.redis),
                description='env-a',
            ),
        )
        self.singleton_redis = get_container_by_service('redis', env_id=self.ready_env.env_id)

    async def given_env_b_with_namespaced_redis(self):
        self.env_b = Environment(self.redis, description='env-b')
        self.namespaced_env_id = get_stable_env_id(self.env_b, 0)

    async def when_user_prepares_env_b(self):
        self.ready_envs = await UberCompose(
            cfg_constants=self.constants,
        ).prepare_parallel_environments(
            config_templates=[self.env_b],
            compose_files=self.compose_files,
            workers_per_env={},
            default_workers_per_env=1,
        )

    async def then_all_containers_should_match_expected_layout(self):
        self.containers = retrieve_all_docker_containers()
        assert self.containers == schema.list.len(2)
        assert self.containers == schema.list([
            ...,
            ContainerSchema % {
                'Id': self.singleton_redis['Id'],
                'Labels': {
                    'com.docker.compose.service': 'redis',
                    Label.ENV_ID: self.ready_env.env_id,
                },
            },
            ...,
        ])
        assert self.containers == schema.list([
            ...,
            ContainerSchema % {
                'Labels': {
                    'com.docker.compose.service': f'redis-{self.namespaced_env_id}',
                    Label.ENV_ID: self.namespaced_env_id,
                },
            },
            ...,
        ])
