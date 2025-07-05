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
"""
        )

    async def given_services(self):
        self.service_1 = Service('s1')

    async def given_external_definition(self):
        self.env_vars = {'ENV_VAR': '[[test_run_id]]'}
        self.service_1_external_envs_redefine = self.service_1.with_env(self.env_vars)

    async def given_test_run_id(self):
        self.test_run_id = 'blabla123'

    async def when_user_up_env_without_params(self):
        self.response = await UberCompose(
            run_id=self.test_run_id
        ).up(
            config_template=Environment(self.service_1),
            services_override=[
                OverridenService(
                    Service('-'), services_envs_fix=[self.service_1_external_envs_redefine],
                )
            ],
            compose_files='docker-compose.yaml',
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
                        '/tmp-envs/default_env_id/docker-compose.yaml',

                    Label.ENV_ID: 'default_env_id',
                    Label.ENV_DESCRIPTION: str(Environment(Service('s1'))),
                    Label.COMPOSE_FILES: ':'.join([
                        f'{self.compose_filename_1}',
                    ]),
                    Label.COMPOSE_FILES_INSTANCE: ':'.join([
                        f'/tmp-envs/default_env_id/{self.compose_filename_1}',
                    ]),
                },
            },
        ])

    async def and_it_should_have_env_var_set(self):
        self.docker_containers = retrieve_dockerish_containers()
        self.container = self.docker_containers[0]
        self.expected_run_ens = {k: v.replace('[[test_run_id]]', self.test_run_id) for k, v in self.env_vars.items()}
        self.expected_envs = [f'{k}={v}' for k, v in self.expected_run_ens.items()]
        assert self.container.attrs['Config']['Env'] == ServiceEnvSchema % [
            ...,
            *self.expected_envs,
            ...,
        ]
