from time import perf_counter

from contexts.compose_file import compose_file
from contexts.isolated_project import isolated_constants
from contexts.isolated_project import isolated_project
from contexts.no_docker_containers import no_docker_containers
from contexts.no_docker_containers import retrieve_all_docker_containers
from d42 import schema
from schemas.docker import ContainerSchema
import vedro
from vedro import catched

from uber_compose import Environment
from uber_compose import Service
from uber_compose.errors.up import ServicesUpError
from uber_compose.helpers.health_policy import UpHealthPolicy
from uber_compose.uber_compose import UberCompose


class Scenario(vedro.Scenario):
    subject = 'up env with exited service without restart policy fails fast'

    async def given_no_docker_containers(self):
        no_docker_containers()

    async def given_isolated_project(self):
        self.project = isolated_project()
        self.instance_files_root = self.project.tmp_envs_path
        self.constants = isolated_constants(self.project)

    async def given_compose_file_with_failing_service_without_restart_policy(self):
        self.compose_filename = 'docker-compose.basic.yaml'
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
        self.started_at = perf_counter()
        with catched(ServicesUpError) as self.exc_info:
            await UberCompose(
                cfg_constants=self.constants,
                health_policy=UpHealthPolicy(
                    service_up_check_attempts=20,
                    service_up_check_delay_s=1,
                    pre_check_delay_s=0,
                ),
            ).up(
                config_template=Environment(
                    'DEFAULT',
                    Service('s1')
                ),
                compose_files='docker-compose.basic.yaml',
            )
        self.elapsed = perf_counter() - self.started_at

    async def then_it_should_fail_without_waiting_for_all_retries(self):
        assert self.elapsed < 10

    async def then_env_should_contain_exited_service(self):
        self.containers = retrieve_all_docker_containers()
        assert self.containers == schema.list([
            ContainerSchema % {
                'State': 'exited',
                'Labels': {
                    'com.docker.compose.service': 's1',
                    'com.docker.compose.project.config_files': (
                        f'{self.instance_files_root}/default_env_id/'
                        f'{self.compose_filename}'
                    ),
                },
            },
        ])
        assert 'Exited (10)' in self.containers[0]['Status']

    async def then_it_should_report_unexpected_exit(self):
        exception_str = str(self.exc_info.value)
        assert "Can't check up services" in exception_str
        assert 'Exited (10)' in exception_str
