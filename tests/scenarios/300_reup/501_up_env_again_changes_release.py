import vedro
from d42 import schema

from contexts.compose_file import compose_file
from contexts.no_docker_compose_files import no_docker_compose_files
from contexts.no_docker_containers import no_docker_containers
from contexts.no_docker_containers import retrieve_all_docker_containers
from contexts.services_started import services_started
from schemas.docker import ContainerSchema
from uber_compose import Environment
from uber_compose import Service
from uber_compose.helpers.bytes_pickle import debase64_pickled
from uber_compose.uber_compose import UberCompose
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

    async def given_environment(self):
        self.environment = Environment(
                Service('s1'),
                description='blahblah',
            )
        self.compose_files = 'docker-compose.yaml'

    async def given_start_env(self):
        self.started_service = await services_started(
            compose_files=self.compose_files,
            config_template=self.environment,
        )
        self.started_containers = retrieve_all_docker_containers()

    async def given_changed_env_service_set(self):
        self.new_environment = Environment(
            Service('s1'),
            Service('s2'),
            description='blahblah',
        )
        self.compose_files = 'docker-compose.yaml'

    async def when_user_up_env_without_params(self):
        self.response = await UberCompose().up(
            compose_files=self.compose_files,
            config_template=self.new_environment,
        )

    async def then_it_should_return_successful_code(self):
        assert self.response.env_id == schema.str
        assert self.response.env == self.new_environment

    async def then_it_should_change_release_id(self):
        assert self.response.release_id != self.started_service.release_id

    async def then_it_should_up_entire_env(self):
        self.containers = retrieve_all_docker_containers()
        assert self.containers == schema.list([
            ...,
            ContainerSchema % {
                'Labels': {
                    Label.RELEASE_ID: self.response.release_id,
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
                    Label.RELEASE_ID: self.response.release_id,
                    'com.docker.compose.service': 's2',
                    'com.docker.compose.project.config_files':
                        '/tmp/uc-envs/default_env_id/docker-compose.yaml',
                },
            },
            ...,
        ])

    async def then_it_should_env_config_template(self):
        self.env_config_template = self.containers[0]['Labels'][Label.ENV_CONFIG_TEMPLATE]
        assert debase64_pickled(self.env_config_template) == Environment.from_environment(self.new_environment)

        self.env_config_template = self.containers[0]['Labels'][Label.ENV_CONFIG]
        assert debase64_pickled(self.env_config_template) == self.new_environment
