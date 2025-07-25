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
        self.healthcheck_result_file = '/tmp/healthcheck'
        self.migration_result_file = '/tmp/migration.log'
        self.migration = {}
        self.services = ['s1', 's2', 's3', 's4']
        for service in self.services:
            self.migration[service] = fake(schema.str.len(1, 10))
        self.service_compose_content = """
version: "3"

services:
  s1:
    image: busybox:stable
    command: 'sh -c "sleep 5 && echo `date +%s` > /tmp/healthcheck; trap : TERM INT; sleep 604800; wait"'
    healthcheck:
      test: ["CMD", "sh", "-c", "[ -f /tmp/healthcheck ] || exit 1"]
      interval: 5s
      timeout: 10s
      retries: 100
    x-migration: 
      - after_start: sh -c 'echo `date +%s` > /tmp/migration.log'
      
  s2:
    image: busybox:stable
    command: 'sh -c "trap : TERM INT; sleep 604800; wait"'
    x-migration: 
      - after_start: sh -c 'echo `date +%s` > /tmp/migration.log'
    depends_on:
      s1:
        condition: service_healthy
"""
        compose_file(
            self.compose_filename,
            content=self.service_compose_content
        )

    async def when_user_up_env_without_params(self):
        self.response = await UberCompose().up(
            compose_files=self.compose_filename,
            config_template=Environment(
                Service('s1'),
                Service('s2'),
            ),
        )

    async def then_it_should_return_successful_code(self):
        assert self.response.env_id == schema.str

    async def then_it_should_up_entire_env(self):
        self.containers = retrieve_all_docker_containers()
        assert self.containers == schema.list([
            ...,
            ContainerSchema % {
                'Labels': {
                    'com.docker.compose.service': 's1',
                    'com.docker.compose.project.config_files': f'/tmp/uc-envs/default_env_id/{self.compose_filename}',
                },
            },
            ...,
        ])
        assert self.containers == schema.list([
            ...,
            ContainerSchema % {
                'Labels': {
                    'com.docker.compose.service': 's2',
                    'com.docker.compose.project.config_files': f'/tmp/uc-envs/default_env_id/{self.compose_filename}',
                },
            },
            ...,
        ])

    @retry(attempts=10, delay=1)
    async def then_it_should_apply_migration_s1_after_start_before_health_check(self):
        self.migration_s1_done_time = int(get_file_from_container('s1', self.migration_result_file))
        self.healthcheck_done_time = int(get_file_from_container('s1', self.healthcheck_result_file))
        assert self.migration_s1_done_time <= self.healthcheck_done_time

    @retry(attempts=10, delay=1)
    async def and_it_should_apply_migration_s2_after_start_same_time_or_later_than_health_check_done(self):
        self.migration_s2_done_time = int(get_file_from_container('s2', self.migration_result_file))
        assert self.healthcheck_done_time <= self.migration_s2_done_time
