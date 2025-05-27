import vedro
from d42 import schema

from vedro import catched

from uber_compose import Environment
from uber_compose import Service

from contexts.compose_file import compose_file
from contexts.no_docker_compose_files import no_docker_compose_files
from contexts.no_docker_containers import no_docker_containers
from contexts.no_docker_containers import retrieve_all_docker_containers
from schemas.docker import ContainerSchema
from uber_compose import UberCompose
from uber_compose.errors.up import ServicesUpError
from uber_compose.helpers.health_policy import UpHealthPolicy
from uber_compose.output.console import DEBUG_LOG_POLICY


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
    command: 'sh -c "exit 10"'
"""
        )

    async def when_user_up_env_with_unexpected_to_exit_service(self):
        with catched(ServicesUpError) as self.exc_info:
            self.response = await UberCompose(
                health_policy=UpHealthPolicy(service_up_check_attempts=3, service_up_check_delay_s=1)
            ).up(
                config_template=Environment(
                    'DEFAULT',
                    Service('s1')
                ),
                compose_files='docker-compose.basic.yaml',
            )

    async def then_it_should_not_up_env(self):
        self.containers = retrieve_all_docker_containers()
        assert self.containers == schema.list([
            ContainerSchema % {
                'State': 'exited',
                'Labels': {
                    'com.docker.compose.service': 's1',
                    'com.docker.compose.project.config_files': f'/tmp-envs/no_id/{self.compose_filename}',
                },
            },
        ])
        assert 'Exited (10)' in self.containers[0]['Status']

    async def then_it_should_out_services_logs(self):
        self.exception_str = str(self.exc_info.value)
        assert "Can't up services" in self.exception_str
        assert "s1" in self.exception_str
        assert "Exited (10)" in self.exception_str
