from contexts.compose_file import compose_file
from contexts.no_docker_compose_files import no_docker_compose_files
from contexts.no_docker_containers import no_docker_containers
from contexts.no_docker_containers import retrieve_all_docker_containers
from contexts.services_started import services_started
from d42 import schema
from schemas.docker import ContainerSchema
import vedro
from vedro import catched

from uber_compose import Env
from uber_compose import Environment
from uber_compose import Service
from uber_compose.helpers.current_env import reset_current_env_id
from uber_compose.helpers.labels import Label
from uber_compose.uber_compose import UberCompose


class Scenario(vedro.Scenario):
    subject = 'exec without env_id in parallel namespaces fails fast instead of picking arbitrary container'

    async def given_no_docker_containers(self):
        no_docker_containers()

    async def given_no_docker_compose_files(self):
        no_docker_compose_files()

    async def given_current_env_reset_for_this_scenario(self):
        vedro.defer(reset_current_env_id)
        reset_current_env_id()

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
"""
        )

    async def given_two_namespaces_of_same_service_are_running(self):
        self.environment_a = Environment(Service('s1', Env({'ENV_MARKER': 'a'})), description='env-a')
        self.environment_b = Environment(Service('s1', Env({'ENV_MARKER': 'b'})), description='env-b')

        self.response_a = await services_started(
            compose_files=self.compose_files,
            config_template=self.environment_a,
            parallelism_limit=2,
        )
        self.response_b = await services_started(
            compose_files=self.compose_files,
            config_template=self.environment_b,
            parallelism_limit=2,
        )

    async def when_user_exec_without_env_id(self):
        with catched(ValueError) as self.exc_info:
            await UberCompose().exec(
                container='s1',
                command='echo $ENV_MARKER',
            )

    async def then_it_should_raise_error_with_available_env_ids(self):
        assert self.exc_info.type is ValueError
        error_message = str(self.exc_info.value)
        assert 'default_env_id' in error_message
        assert self.response_a.env_id in error_message
        assert self.response_b.env_id in error_message
        assert 'Pass env_id explicitly' in error_message

    async def then_both_namespaces_should_stay_running(self):
        assert retrieve_all_docker_containers() == schema.list([
            ...,
            ContainerSchema % {
                'Labels': {
                    'com.docker.compose.service': f's1-{self.response_a.env_id}',
                    Label.ENV_ID: self.response_a.env_id,
                    Label.TEMPLATE_SERVICE_NAME: 's1',
                },
            },
            ...,
        ])
        assert retrieve_all_docker_containers() == schema.list([
            ...,
            ContainerSchema % {
                'Labels': {
                    'com.docker.compose.service': f's1-{self.response_b.env_id}',
                    Label.ENV_ID: self.response_b.env_id,
                    Label.TEMPLATE_SERVICE_NAME: 's1',
                },
            },
            ...,
        ])
        assert len(retrieve_all_docker_containers()) == 2
