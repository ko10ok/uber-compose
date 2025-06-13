import vedro
from contexts.compose_file import compose_file
from contexts.no_docker_compose_files import no_docker_compose_files
from contexts.no_docker_containers import no_docker_containers
from contexts.no_docker_containers import retrieve_all_docker_containers
from contexts.no_docker_containers import retrieve_dockerish_containers
from d42 import schema
from schemas.docker import ContainerSchema
from schemas.service_env import ServiceEnvSchema
from uber_compose.env_description.env_types import Env
from uber_compose.env_description.env_types import Environment
from uber_compose.env_description.env_types import Service
from uber_compose.helpers.labels import Label
from uber_compose.uber_compose import UberCompose


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

    async def given_env_var_set(self):
        self.env_var = Env({'ENV_VAR': '%(s2)'})
        self.service_map = {'s2': 's2'}

    async def when_user_up_env_without_params(self):
        self.response = await self.uber_compose_client.up(
            config_template=Environment(Service('s2', env=self.env_var)),
            compose_files='docker-compose.yaml:docker-compose.dev.yaml',
        )

    async def then_it_should_return_successful_code(self):
        assert self.response.env_id == schema.str

    async def then_it_should_up_s2_only(self):
        self.containers = retrieve_all_docker_containers()
        assert self.containers == schema.list([
            ContainerSchema % {
                'Labels': {
                    'com.docker.compose.service': 's2',
                    'com.docker.compose.project.config_files':
                        '/tmp-envs/no_id/docker-compose.yaml,/tmp-envs/no_id/docker-compose.dev.yaml',

                    Label.ENV_ID: 'no_id',
                    Label.ENV_DESCRIPTION: str(Environment(Service('s2'))),
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

    async def and_it_should_have_env_var_set(self):
        self.docker_containers = retrieve_dockerish_containers()
        self.container = self.docker_containers[0]
        self.expected_envs = [f'{k}={v.format(self.service_map)}' for k, v in self.env_var.items()]
        assert self.container.attrs['Config']['Env'] == ServiceEnvSchema % [
            ...,
            *self.expected_envs,
            ...,
        ]
