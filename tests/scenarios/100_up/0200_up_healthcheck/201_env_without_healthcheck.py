import vedro
from d42 import fake
from d42 import schema

from contexts.compose_file import compose_file
from contexts.no_docker_compose_files import no_docker_compose_files
from contexts.no_docker_containers import no_docker_containers
from contexts.no_docker_containers import retrieve_all_docker_containers
from schemas.docker import ContainerSchema
from schemas.env_name import EnvNameSchema
from schemas.http_codes import HTTPStatusCodeOk
from uber_compose import Service
from uber_compose import UberCompose
from uber_compose.env_description.env_types import Environment
from uber_compose.helpers.labels import Label


class Scenario(vedro.Scenario):
    async def no_docker_containers(self):
        no_docker_containers()

    async def no_docker_copose_files(self):
        no_docker_compose_files()

    async def given_compose_file_with_service_with_migration(self):
        self.compose_filename = 'docker-compose.basic.yaml'
        self.migration_result_file = '/tmp/migration.log'
        compose_file(
            self.compose_filename,
            content="""
version: "3"

services:
  s1:
    image: busybox:stable
    command: 'sh -c "trap : TERM INT; sleep 604800; wait"'
"""
        )

    async def when_user_up_env_with_expected_to_exit_service(self):
        self.response = await UberCompose().up(
            config_template=Environment(
                'DEFAULT',
                Service('s1')
            ),
            compose_files='docker-compose.basic.yaml'
        )

    async def then_it_should_return_successful_env_id(self):
        assert self.response.env_id == schema.str

    async def then_it_should_up_entire_env(self):
        self.containers = retrieve_all_docker_containers()
        assert self.containers == schema.list([
            ContainerSchema % {
                'State': 'running',
                'Labels': {
                    Label.SERVICE_NAME: 's1',
                },
            },
        ])
