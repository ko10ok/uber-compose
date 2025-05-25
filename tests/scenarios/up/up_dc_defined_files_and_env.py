import vedro
from d42 import fake
from d42 import schema

from contexts.compose_file import compose_file
from contexts.no_docker_compose_files import no_docker_compose_files
from contexts.no_docker_containers import no_docker_containers
from contexts.no_docker_containers import retrieve_all_docker_containers
from libs.env_const import AUTO_SCANNED_FULL
from schemas.docker import ContainerSchema
from uber_compose import UberCompose
from uber_compose.env_description.env_types import Environment
from uber_compose.env_description.env_types import Service
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

    async def given_client(self):
        self.uber_compose_client = UberCompose()

    async def given_env_description(self):
        self.desc = fake(schema.str('') | schema.str('a a'))

    async def when_user_up_env_without_params(self):
        self.response = await self.uber_compose_client.up(
            config_template=Environment(Service('s2'), description=self.desc),
            compose_files='docker-compose.yaml:docker-compose.dev.yaml',
        )

    async def then_it_should_return_successful_code(self):
        assert self.response == schema.str

    async def then_it_should_up_s2_only(self):
        self.containers = retrieve_all_docker_containers()
        assert self.containers == schema.list([
            ContainerSchema % {
                'Labels': {
                    'com.docker.compose.service': 's2',
                    'com.docker.compose.project.config_files':
                        '/tmp-envs/no_id/docker-compose.yaml,/tmp-envs/no_id/docker-compose.dev.yaml',

                    Label.ENV_ID: 'no_id',
                    Label.ENV_DESCRIPTION: self.desc,
                    Label.COMPOSE_FILES: ':'.join([
                        f'{self.compose_filename_1}',
                        f'{self.compose_filename_2}',
                    ]),
                    Label.COMPOSE_FILES_INSTANCE: ':'.join([
                        f'/tmp-envs/no_id/{self.compose_filename_1}',
                        f'/tmp-envs/no_id/{self.compose_filename_2}',
                    ]),
                },
            },
        ])
