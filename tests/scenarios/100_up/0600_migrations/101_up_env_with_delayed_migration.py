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
    image: python:3.12
    command: 'sh -c "trap : TERM INT; sleep 604800; wait"'
    x-migration:
      - after_start: sh -c "python3 -c \\"import time; time.sleep(3); print(time.time())\\" >> /tmp/migration.log"
      - after_start: sh -c "python3 -c \\"import time; time.sleep(3); print(time.time())\\" >> /tmp/migration.log"
      - after_start: sh -c "python3 -c \\"import time; time.sleep(3); print(time.time())\\" >> /tmp/migration.log"
"""
        )

    async def when_user_up_env_without_params(self):
        self.response = await UberCompose().up(
            compose_files=self.compose_filename,
            config_template=Environment(
                Service('s1')
            )
        )

    async def then_it_should_return_successful_code(self):
        assert self.response.env_id == schema.str

    async def then_it_should_up_entire_env(self):
        self.containers = retrieve_all_docker_containers()
        assert self.containers == schema.list([
            ContainerSchema % {
                'Labels': {
                    'com.docker.compose.service': 's1',
                },
            },
        ])

    @retry(attempts=3, delay=1)
    async def then_it_should_apply_migration(self):
        self.migration_file_content = get_file_from_container('s1', self.migration_result_file)
        self.times = [int(float(t)) for t in self.migration_file_content.decode('utf-8').strip().split('\n')]
        assert self.times[1] - self.times[0] >= 3
        assert self.times[2] - self.times[1] >= 3
