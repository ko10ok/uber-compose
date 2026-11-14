from contexts.compose_file import compose_file
from contexts.isolated_project import isolated_constants
from contexts.isolated_project import isolated_project
from contexts.no_docker_containers import no_docker_containers
import vedro
from vedro import catched

from uber_compose import Environment
from uber_compose import Service
from uber_compose.errors.up import ServicesUpError
from uber_compose.helpers.health_policy import UpHealthPolicy
from uber_compose.uber_compose import UberCompose


class Scenario(vedro.Scenario):
    subject = 'up env writes failed service logs in separate file sections'

    async def given_no_docker_containers(self):
        no_docker_containers()

    async def given_isolated_project(self):
        self.project = isolated_project()
        self.log_path = self.project.tmp_envs_path / 'uber-compose.log'
        self.constants = isolated_constants(
            self.project,
            log_file_path=self.log_path,
        )

    async def given_compose_file_with_failing_service(self):
        self.compose_files = 'docker-compose.yaml'
        compose_file(
            self.compose_files,
            content="""
version: "3"

services:
  s1:
    image: busybox:stable
    command: 'sh -c "echo BAD_EXIT_LOG_LINE; exit 10"'
"""
        )

    async def when_user_up_env_with_failing_service(self):
        with catched(ServicesUpError):
            await UberCompose(
                cfg_constants=self.constants,
                health_policy=UpHealthPolicy(
                    service_up_check_attempts=20,
                    service_up_check_delay_s=0.1,
                    pre_check_delay_s=0,
                ),
            ).up(
                compose_files=self.compose_files,
                config_template=Environment(Service('s1'), description='env-a'),
            )
        self.file_logs = self.log_path.read_text()

    async def then_failed_service_logs_should_be_written_in_separate_section(self):
        assert '===== Logs for failed service s1 (exit code 10) =====' in self.file_logs
        assert '===== End of logs for failed service s1 =====' in self.file_logs

    async def and_section_should_contain_service_logs(self):
        assert 'BAD_EXIT_LOG_LINE' in self.file_logs
