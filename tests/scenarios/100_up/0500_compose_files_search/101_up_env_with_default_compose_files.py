import vedro
from d42 import schema

from contexts.compose_file import compose_file
from contexts.no_docker_compose_files import no_docker_compose_files
from contexts.no_docker_containers import no_docker_containers
from contexts.no_docker_containers import retrieve_all_docker_containers
from libs.env_const import AUTO_SCANNED_FULL
from schemas.docker import ContainerSchema
from schemas.http_codes import HTTPStatusCodeOk
from uber_compose.uber_compose import UberCompose
from uber_compose.helpers.labels import Label


class Scenario(vedro.Scenario):
    async def no_docker_containers(self):
        no_docker_containers()

    async def no_docker_copose_files(self):
        no_docker_compose_files()

    async def given_compose_file_with_service_with_migration(self):
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
        self.compose_filename_2 = 'tests/e2e/docker-compose.yaml'
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
        self.compose_filename_3 = 'tests/e2e/unreachable/docker-compose.yaml'
        compose_file(
            self.compose_filename_3,
            content="""
version: "3"

services:
  s3:
    image: busybox:stable
    command: 'sh -c "trap : TERM INT; sleep 604800; wait"'
"""
        )

    async def when_user_up_env_without_params(self):
        self.response = await UberCompose().up()

    async def then_it_should_return_successful_code(self):
        assert self.response.env_id == schema.str

    async def and_it_should_up_s1_env_service(self):
        self.containers = retrieve_all_docker_containers()
        assert self.containers == schema.list([
            ...,
            ContainerSchema % {
                'Labels': {
                    'com.docker.compose.service': 's1',

                    Label.ENV_ID: 'no_id',
                    Label.ENV_DESCRIPTION: AUTO_SCANNED_FULL,
                    Label.COMPOSE_FILES: ':'.join(sorted([
                        f'{self.compose_filename_1}',
                        f'{self.compose_filename_2}',
                    ])),
                    Label.COMPOSE_FILES_INSTANCE: ':'.join(sorted([
                        f'/tmp-envs/no_id/{self.compose_filename_1}',
                        f'/tmp-envs/no_id/{self.compose_filename_2.replace("/", "-")}',
                    ]))
                },
            },
            ...,
        ])

    async def and_it_should_up_s2_env_service(self):
        self.containers = retrieve_all_docker_containers()
        assert self.containers == schema.list([
            ...,
            ContainerSchema % {
                'Labels': {
                    'com.docker.compose.service': 's2',

                    Label.ENV_ID: 'no_id',
                    Label.ENV_DESCRIPTION: AUTO_SCANNED_FULL,

                    Label.COMPOSE_FILES: ':'.join(sorted([
                        f'{self.compose_filename_1}',
                        f'{self.compose_filename_2}',
                    ])),
                    Label.COMPOSE_FILES_INSTANCE: ':'.join(sorted([
                        f'/tmp-envs/no_id/{self.compose_filename_1}',
                        f'/tmp-envs/no_id/{self.compose_filename_2.replace("/", "-")}',
                    ])),
                },
            },
            ...,
        ])
