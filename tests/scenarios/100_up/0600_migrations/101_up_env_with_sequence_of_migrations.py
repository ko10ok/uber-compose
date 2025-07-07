import vedro
from d42 import fake
from d42 import schema
from rtry import retry

from contexts.compose_file import compose_file
from contexts.no_docker_compose_files import no_docker_compose_files
from contexts.no_docker_containers import no_docker_containers
from contexts.no_docker_containers import retrieve_all_docker_containers
from helpers.docker_migration_result import get_file_from_container
from uber_compose.uber_compose import UberCompose
from uber_compose import Environment
from uber_compose import Service


from schemas.docker import ContainerSchema
from schemas.env_name import EnvNameSchema
from schemas.http_codes import HTTPStatusCodeOk


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
    x-migration:
      - after_start: sh -c 'sleep 3 && echo 1 >> /tmp/migration.log'
      - after_start: sh -c 'sleep 10 && echo 13 >> /tmp/migration.log &'
      - after_start: sh -c 'sleep 10 && echo 66 >> /tmp/migration.log & '
      - after_start: sh -c 'echo 2 >> /tmp/migration.log'
"""
        )

    async def when_user_up_env_without_params(self):
        self.response = await UberCompose().up(
            compose_files=self.compose_filename,
            config_template=Environment(
                Service('s1')
            ),
        )

    async def then_it_should_return_successful_code(self):
        assert self.response.env_id == schema.str

    async def then_it_should_up_entire_env(self):
        self.containers = retrieve_all_docker_containers()
        assert self.containers == schema.list([
            ContainerSchema % {
                'Labels': {
                    'com.docker.compose.service': 's1',
                    'com.docker.compose.project.config_files': f'/tmp/uc-envs/default_env_id/{self.compose_filename}',
                },
            },
        ])

    @retry(attempts=3, delay=1)
    async def then_it_should_apply_migration(self):
        self.migration_file_content = get_file_from_container('s1', self.migration_result_file)
        assert self.migration_file_content == schema.bytes % (b'1\n'
                                                              b'2\n')
