import vedro
from d42 import schema

from contexts.compose_file import compose_file
from contexts.no_docker_compose_files import no_docker_compose_files
from contexts.no_docker_containers import no_docker_containers
from contexts.no_docker_containers import retrieve_all_docker_containers
from libs.env_const import AUTO_SCANNED
from schemas.docker import ContainerSchema
from uber_compose import Environment
from uber_compose import Service
from uber_compose.helpers.bytes_pickle import base64_pickled
from uber_compose.helpers.bytes_pickle import debase64_pickled
from uber_compose.uber_compose import UberCompose
from uber_compose.helpers.labels import Label


class Scenario(vedro.Scenario):
    async def no_docker_containers(self):
        no_docker_containers()

    async def no_docker_copose_files(self):
        no_docker_compose_files()

    async def given_compose_files(self):
        self.compose_filename_1 = 'docker-compose.yaml'
        compose_file(
            self.compose_filename_1,
            content="""
version: "3"

services:
  s1:
    image: busybox:stable
    command: 'sh -c "trap : TERM INT; sleep 604800; wait"'
"""
        )

        self.compose_filename_2 = 'docker-compose.dev.yaml'
        compose_file(
            self.compose_filename_2,
            content="""
version: "3"

services:
  s2:
    image: busybox:stable
    command: 'sh -c "trap : TERM INT; sleep 604800; wait"'
"""
        )

    async def when_user_up_env_without_params(self):
        self.response = await UberCompose().up()

    async def then_it_should_return_successful_code(self):
        assert self.response.env_id == schema.str


    async def then_it_should_up_s1(self):
        self.containers = retrieve_all_docker_containers()
        assert self.containers == schema.list([
            ...,
            ContainerSchema % {
                'Labels': {
                    'com.docker.compose.service': 's1',
                    'com.docker.compose.project.config_files': ','.join(sorted([
                        f'/tmp-envs/default_env_id/{self.compose_filename_1}',
                        f'/tmp-envs/default_env_id/{self.compose_filename_2}',
                    ])),

                    Label.ENV_ID: 'default_env_id',
                    Label.ENV_DESCRIPTION: AUTO_SCANNED,
                    Label.COMPOSE_FILES: ':'.join(sorted([
                        f'{self.compose_filename_1}',
                        f'{self.compose_filename_2}',
                    ])),
                    Label.COMPOSE_FILES_INSTANCE: ':'.join(sorted([
                        f'/tmp-envs/default_env_id/{self.compose_filename_1}',
                        f'/tmp-envs/default_env_id/{self.compose_filename_2}',
                    ])),
                    Label.SERVICE_NAME: 's1',
                },
            },
            ...
        ])

    async def then_it_should_up_s2(self):
        self.containers = retrieve_all_docker_containers()
        assert self.containers == schema.list([
            ...,
            ContainerSchema % {
                'Labels': {
                    'com.docker.compose.service': 's2',
                    'com.docker.compose.project.config_files': ','.join(sorted([
                        f'/tmp-envs/default_env_id/{self.compose_filename_1}',
                        f'/tmp-envs/default_env_id/{self.compose_filename_2}',
                    ])),

                    Label.ENV_ID: 'default_env_id',
                    Label.ENV_DESCRIPTION: AUTO_SCANNED,
                    Label.COMPOSE_FILES: ':'.join(sorted([
                        f'{self.compose_filename_1}',
                        f'{self.compose_filename_2}',
                    ])),
                    Label.COMPOSE_FILES_INSTANCE: ':'.join(sorted([
                        f'/tmp-envs/default_env_id/{self.compose_filename_1}',
                        f'/tmp-envs/default_env_id/{self.compose_filename_2}',
                    ])),
                    Label.SERVICE_NAME: 's2',
                },
            },
            ...
        ])

    async def then_it_should_env_config_template(self):
        self.env_config_template = self.containers[0]['Labels'][Label.ENV_CONFIG_TEMPLATE]
        assert debase64_pickled(self.env_config_template) == Environment(
            Service('s1'),
            Service('s2'),
        )

        self.env_config_template = self.containers[0]['Labels'][Label.ENV_CONFIG]
        assert debase64_pickled(self.env_config_template) == Environment(
            Service('s1'),
            Service('s2'),
            description=AUTO_SCANNED
        )
