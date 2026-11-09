from contexts.compose_file import compose_file
from contexts.isolated_project import isolated_constants
from contexts.isolated_project import isolated_project
from contexts.no_docker_containers import no_docker_containers
from contexts.no_docker_containers import retrieve_all_docker_containers
from d42 import schema
from helpers.docker_container import get_containers_by_env_id
from helpers.docker_container import get_env_snapshot
from schemas.docker import ContainerSchema
import vedro

from uber_compose import Environment
from uber_compose import Service
from uber_compose.core.utils.compose_instance_cfg import get_stable_env_id
from uber_compose.helpers.labels import Label
from uber_compose.uber_compose import UberCompose


class Scenario(vedro.Scenario):
    subject = 'prepare decreased replicas of env a does not touch env b'

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

    async def given_two_replicas_of_each_env_are_prepared(self):
        self.environment_a = Environment(Service('s1'), description='env-a')
        self.environment_b = Environment(Service('s1'), description='env-b')
        self.env_id_a_0 = get_stable_env_id(self.environment_a, 0)
        self.env_id_a_1 = get_stable_env_id(self.environment_a, 1)
        self.env_id_b_0 = get_stable_env_id(self.environment_b, 0)
        self.env_id_b_1 = get_stable_env_id(self.environment_b, 1)

        await UberCompose(cfg_constants=self.constants).prepare_parallel_environments(
            config_templates=[self.environment_a, self.environment_b],
            compose_files=self.compose_files,
            workers_per_env={'env-a': 2, 'env-b': 2},
        )
        self.snapshot_b_0 = get_env_snapshot(self.env_id_b_0)
        self.snapshot_b_1 = get_env_snapshot(self.env_id_b_1)

    async def when_user_prepares_one_replica_of_env_a(self):
        self.ready_envs = await UberCompose(cfg_constants=self.constants).prepare_parallel_environments(
            config_templates=[self.environment_a, self.environment_b],
            compose_files=self.compose_files,
            workers_per_env={'env-a': 1, 'env-b': 2},
        )

    async def then_collect_all_containers(self):
        self.containers = retrieve_all_docker_containers()

    async def then_env_a_should_have_only_one_replica(self):
        assert len(get_containers_by_env_id(self.env_id_a_0, self.containers)) == 1
        assert get_containers_by_env_id(self.env_id_a_1, self.containers) == []

    async def then_env_b_should_still_have_two_replicas(self):
        assert len(get_containers_by_env_id(self.env_id_b_0, self.containers)) == 1
        assert len(get_containers_by_env_id(self.env_id_b_1, self.containers)) == 1

    async def then_env_b_should_be_untouched(self):
        for container_id, container_state in self.snapshot_b_0.items():
            assert self.containers == schema.list([
                ...,
                ContainerSchema % {
                    'Id': container_id,
                    'State': container_state['State'],
                    'Labels': {
                        'com.docker.compose.service': container_state['Service'],
                        Label.ENV_ID: self.env_id_b_0,
                    },
                },
                ...,
            ])
        for container_id, container_state in self.snapshot_b_1.items():
            assert self.containers == schema.list([
                ...,
                ContainerSchema % {
                    'Id': container_id,
                    'State': container_state['State'],
                    'Labels': {
                        'com.docker.compose.service': container_state['Service'],
                        Label.ENV_ID: self.env_id_b_1,
                    },
                },
                ...,
            ])
