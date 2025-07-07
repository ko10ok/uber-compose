from uuid import uuid4

import vedro
from d42 import fake
from d42 import schema

from contexts.compose_file import compose_file
from contexts.no_docker_compose_files import no_docker_compose_files
from contexts.no_docker_containers import no_docker_containers
from contexts.no_docker_containers import retrieve_all_docker_containers
from contexts.services_started import services_started
from schemas.docker import ContainerSchema
from schemas.env_name import EnvNameSchema
from uber_compose import Environment
from uber_compose import Service
from uber_compose.uber_compose import UberCompose
from uber_compose.env_description.env_types import Env
from uber_compose.helpers.labels import Label


class Scenario(vedro.Scenario):
    async def no_docker_containers(self):
        no_docker_containers()

    async def no_docker_copose_files(self):
        no_docker_compose_files()

    async def given_compose_files(self):
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
"""
        )

    async def given_start_env(self):
        self.start_release = str(uuid4())
        self.env_name = fake(EnvNameSchema)
        self.started_service = await services_started(
            compose_files='docker-compose.yaml',
            config_template=Environment(
                Service('s1'),
                Service('s2'),
            ),
            release_id=self.start_release,
        )
        self.started_containers = retrieve_all_docker_containers()

    async def given_not_changed_compose_files(self):
        pass

    async def given_next_run_release(self):
        self.next_release = str(uuid4())

    async def when_user_up_env_without_params(self):
        self.response = await UberCompose().up(
            compose_files='docker-compose.yaml',
            config_template=Environment(
                Service('s1', Env({'A': '1'})),
                Service('s2')
            ),
            release_id=self.next_release,
        )

    async def then_it_should_return_successful_code(self):
        assert self.response.env_id == schema.str

    async def then_it_should_up_entire_env(self):
        self.containers = retrieve_all_docker_containers()
        assert self.containers == schema.list([
            ...,
            ContainerSchema % {
                'Labels': {
                    Label.RELEASE_ID: self.next_release,
                    'com.docker.compose.service': 's1',
                    'com.docker.compose.project.config_files':
                        '/tmp/uc-envs/default_env_id/docker-compose.yaml',
                },
            },
            ...,
        ])
        assert self.containers == schema.list([
            ...,
            ContainerSchema % {
                'Labels': {
                    Label.RELEASE_ID: self.next_release,
                    'com.docker.compose.service': 's2',
                    'com.docker.compose.project.config_files':
                        '/tmp/uc-envs/default_env_id/docker-compose.yaml',
                },
            },
            ...,
        ])
