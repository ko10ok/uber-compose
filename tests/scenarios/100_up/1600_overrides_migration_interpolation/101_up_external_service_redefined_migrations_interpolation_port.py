import vedro
from contexts.no_docker_containers import retrieve_dockerish_containers
from d42 import fake
from d42 import schema

from contexts.compose_file import compose_file
from contexts.no_docker_compose_files import no_docker_compose_files
from contexts.no_docker_containers import no_docker_containers
from contexts.no_docker_containers import retrieve_all_docker_containers
from helpers.docker_migration_result import get_file_from_container
from libs.env_const import AUTO_SCANNED
from uber_compose.output.console import LogPolicy
from schemas.docker import ContainerSchema
from schemas.service_env import ServiceEnvSchema
from uber_compose import OverridenService
from uber_compose.uber_compose import UberCompose
from uber_compose.env_description.env_types import Environment
from uber_compose.env_description.env_types import Service
from uber_compose.helpers.labels import Label


@vedro.skip()
class Scenario(vedro.Scenario):
    async def no_docker_containers(self):
        no_docker_containers()

    async def no_docker_copose_files(self):
        no_docker_compose_files()

    async def given_compose_files(self):
        self.compose_filename_1 = 'docker-compose.yaml'
        self.migration_result_file = '/tmp/migration.log'
        compose_file(
            self.compose_filename_1,
            content="""
version: "3"

services:
  s1:
    image: busybox:stable
    command: 'sh -c "trap : TERM INT; sleep 604800; wait"'
    environment:
        - ENV_VAR_HOST=s2
    x-migration:
      - after_start: sh -c "echo envvar-\${ENV_VAR_HOST} >> /tmp/migration.log"
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

    async def given_external_definition(self):
        self.env_vars = {'ENV_VAR_HOST': 'external_s2_%(port_9092)s_end'}
        self.service_1_external_envs_redefine = self.service_1.with_env(self.env_vars)

    async def when_user_up_env_without_params(self):
        self.response = await UberCompose().up(
            config_template=Environment.from_environment(
                Environment(Service('s1'), Service('s2')),
                services_override=[
                    OverridenService(
                        Service('s2'), services_envs_fix=[self.service_1_external_envs_redefine],
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
            ContainerSchema % {
                'Labels': {
                    'com.docker.compose.service': 's1',
                    'com.docker.compose.project.config_files':
                        '/tmp-envs/default_env_id/docker-compose.yaml,/tmp-envs/default_env_id/docker-compose.dev.yaml',

                    Label.ENV_ID: 'default_env_id',
                    Label.ENV_DESCRIPTION: str(Environment(Service('s1'), Service('s2'))),
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
        ])

    async def and_it_should_have_env_var_set(self):
        self.docker_containers = retrieve_dockerish_containers()
        self.container = self.docker_containers[0]
        self.expected_envs = [f'{k}={v}' for k, v in self.env_vars.items()]
        assert self.container.attrs['Config']['Env'] == ServiceEnvSchema % [
            ...,
            *self.expected_envs,
            ...,
        ]

    async def then_it_should_apply_migration(self):
        self.migration_file_content = get_file_from_container('s1', self.migration_result_file)
        assert self.migration_file_content == schema.bytes % (b'envvar-external_s2\n')
