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

from uber_compose import Env
from uber_compose import Environment
from uber_compose import Service
from uber_compose.helpers.labels import Label


class Scenario(vedro.Scenario):
    subject = 'up changed template with same env id does not touch neighbour env'

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
        )
        self.snapshot_a = get_env_snapshot(self.env_id_a)
        self.containers_b_before = retrieve_all_docker_containers()
        self.ids_b_before = {
            container['Id']
            for container in self.containers_b_before
            if container['Labels'].get(Label.ENV_ID) == self.env_id_b
        }

    async def when_user_up_env_b_with_changed_template(self):
        self.changed_environment_b = Environment(
            Service('s1', Env({'MARKER': 'new'})),
            Service('s2'),
            description='env-b',
        )
        self.response_b_changed = await services_started(
            constants=self.constants,
            compose_files=self.compose_files,
            config_template=self.changed_environment_b,
            parallelism_limit=2,
            env_id=self.env_id_b,
        )

    async def then_collect_all_containers(self):
        self.containers = retrieve_all_docker_containers()

    async def then_env_b_should_keep_requested_env_id(self):
        assert self.response_b.env_id == self.env_id_b
        assert self.response_b_changed.env_id == self.env_id_b

    async def then_env_b_containers_should_be_recreated(self):
        containers_b_after = {
            container['Id']
            for container in self.containers
            if container['Labels'].get(Label.ENV_ID) == self.env_id_b
        }
        assert len(containers_b_after) == 2
        assert self.ids_b_before.isdisjoint(containers_b_after)

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
