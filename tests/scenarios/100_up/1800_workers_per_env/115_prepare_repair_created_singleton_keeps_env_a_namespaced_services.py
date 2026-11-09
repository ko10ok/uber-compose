from contexts.compose_file import compose_file
from contexts.isolated_project import isolated_constants
from contexts.isolated_project import isolated_project
from contexts.no_docker_containers import created_docker_container
from contexts.no_docker_containers import no_docker_containers
from contexts.no_docker_containers import retrieve_all_docker_containers
from helpers.docker_container import get_container_by_service
from helpers.docker_container import get_containers_by_env_id
import vedro

from uber_compose import Environment
from uber_compose import Service
from uber_compose.core.utils.compose_instance_cfg import get_stable_env_id
from uber_compose.env_description.env_tools import singleton
from uber_compose.uber_compose import UberCompose


class Scenario(vedro.Scenario):
    subject = 'prepare repairs created singleton and keeps env a running'

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

  app:
    image: busybox:stable
    command: 'sh -c "trap : TERM INT; sleep 604800; wait"'
"""
        )

    async def given_env_a_and_env_b_with_shared_singleton_are_prepared(self):
        self.environment_a = Environment(
            singleton(Service('redis')),
            Service('app'),
            description='env-a',
        )
        self.environment_b = Environment(
            singleton(Service('redis')),
            Service('app'),
            description='env-b',
        )
        self.env_id_a = get_stable_env_id(self.environment_a, 0)
        self.env_id_b = get_stable_env_id(self.environment_b, 0)

        await UberCompose(cfg_constants=self.constants).prepare_parallel_environments(
            config_templates=[self.environment_a, self.environment_b],
            compose_files=self.compose_files,
            workers_per_env={'env-a': 1, 'env-b': 1},
        )

    async def given_singleton_is_stuck_in_created_state(self):
        created_docker_container('redis')

    async def when_user_repares_env_b(self):
        self.ready_envs = await UberCompose(cfg_constants=self.constants).prepare_parallel_environments(
            config_templates=[self.environment_a, self.environment_b],
            compose_files=self.compose_files,
            workers_per_env={'env-a': 1, 'env-b': 1},
        )

    async def then_collect_all_containers(self):
        self.containers = retrieve_all_docker_containers()

    async def then_singleton_should_be_running_once(self):
        assert get_container_by_service('redis', containers=self.containers)['State'] == 'running'

    async def then_env_a_namespaced_service_should_be_running(self):
        containers_a = [
            container
            for container in get_containers_by_env_id(self.env_id_a, self.containers)
            if container['Labels'].get('com.docker.compose.service') == f'app-{self.env_id_a}'
        ]
        assert len(containers_a) == 1
        assert containers_a[0]['State'] == 'running'
