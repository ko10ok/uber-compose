import vedro
from contexts.no_docker_containers import retrieve_dockerish_containers
from d42 import fake
from d42 import schema

from contexts.compose_file import compose_file
from contexts.no_docker_compose_files import no_docker_compose_files
from contexts.no_docker_containers import no_docker_containers
from contexts.no_docker_containers import retrieve_all_docker_containers
from libs.env_const import AUTO_SCANNED
from schemas.docker import ContainerSchema
from schemas.service_env import ServiceEnvSchema
from uber_compose import OverridenService
from uber_compose.uber_compose import UberCompose
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
    environment:
        - ENV_VAR=s2
        
  s3:
    image: busybox:stable
    command: 'sh -c "trap : TERM INT; sleep 604800; wait"' 
    environment:
      - ENV_VAR=s2
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
    async def given_services(self):
        self.service_1 = Service('s1')
        self.service_2 = Service('s2')
        self.service_3 = Service('s3')

    async def given_external_definition(self):
        self.env_vars = {'ENV_VAR': 'external_s2'}

    async def when_user_up_env_without_params(self):
        self.response = await UberCompose().up(
            config_template=Environment.from_environment(
                Environment(Service('s1'), Service('s2'), Service('s3')),
                services_override=[
                    OverridenService(
                        Service('s2'), services_envs_fix=[Service('*', env=self.env_vars)],
                    )
                ],
            ),
            compose_files='docker-compose.yaml:docker-compose.dev.yaml',
        )

    async def then_it_should_return_successful_code(self):
        assert self.response.env_id == schema.str

    async def then_it_should_up_s1(self):
        self.containers = retrieve_all_docker_containers()
        assert self.containers == schema.list([
            ...,
            ContainerSchema % {
                'Labels': {
                    'com.docker.compose.service': 's1',
                    'com.docker.compose.project.config_files':
                        '/tmp-envs/default_env_id/docker-compose.yaml,/tmp-envs/default_env_id/docker-compose.dev.yaml',

                    Label.ENV_ID: 'default_env_id',
                    Label.ENV_DESCRIPTION: str(Environment(Service('s1'), Service('s2'), Service('s3'))),
                    Label.COMPOSE_FILES: ':'.join([
                        f'{self.compose_filename_1}',
                        f'{self.compose_filename_2}',
                    ]),
                    Label.COMPOSE_FILES_INSTANCE: ':'.join([
                        f'/tmp-envs/default_env_id/{self.compose_filename_1}',
                        f'/tmp-envs/default_env_id/{self.compose_filename_2}',
                    ]),
                },
            },
            ...,
        ])

    async def then_it_should_up_s3(self):
        self.containers = retrieve_all_docker_containers()
        assert self.containers == schema.list([
            ...,
            ContainerSchema % {
                'Labels': {
                    'com.docker.compose.service': 's3',
                    'com.docker.compose.project.config_files':
                        '/tmp-envs/default_env_id/docker-compose.yaml,/tmp-envs/default_env_id/docker-compose.dev.yaml',

                    Label.ENV_ID: 'default_env_id',
                    Label.ENV_DESCRIPTION: str(Environment(Service('s1'), Service('s2'), Service('s3'))),
                    Label.COMPOSE_FILES: ':'.join([
                        f'{self.compose_filename_1}',
                        f'{self.compose_filename_2}',
                    ]),
                    Label.COMPOSE_FILES_INSTANCE: ':'.join([
                        f'/tmp-envs/default_env_id/{self.compose_filename_1}',
                        f'/tmp-envs/default_env_id/{self.compose_filename_2}',
                    ]),
                },
            },
            ...,
        ])

    async def and_it_should_have_env_s1_s3_var_set(self):
        self.docker_containers = retrieve_dockerish_containers()
        self.expected_envs = {
            's1': [f'{k}={v}' for k, v in self.env_vars.items()],
            's3': [f'{k}={v}' for k, v in self.env_vars.items()]
        }
        for container in self.docker_containers:
            assert container.attrs['Config']['Env'] == ServiceEnvSchema % [
                ...,
                *self.expected_envs[container.labels[Label.SERVICE_NAME]],
                ...,
            ]
