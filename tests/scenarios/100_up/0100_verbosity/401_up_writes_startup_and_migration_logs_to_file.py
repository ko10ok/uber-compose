from contextlib import redirect_stdout
from io import StringIO

from contexts.compose_file import compose_file
from contexts.isolated_project import isolated_constants
from contexts.isolated_project import isolated_project
from contexts.no_docker_containers import no_docker_containers
from d42 import schema
import vedro

from uber_compose.env_description.env_types import Environment
from uber_compose.env_description.env_types import Service
from uber_compose.uber_compose import UberCompose


class Scenario(vedro.Scenario):
    subject = 'up env writes startup and migration logs to file with default policy'

    async def given_no_docker_containers(self):
        no_docker_containers()

    async def given_isolated_project(self):
        self.project = isolated_project()
        self.log_path = self.project.tmp_envs_path / 'uber-compose.log'
        self.constants = isolated_constants(
            self.project,
            log_file_path=self.log_path,
        )

    async def given_compose_file(self):
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

    async def when_user_up_env_with_default_log_policy(self):
        self.stdout_stream = StringIO()
        with redirect_stdout(self.stdout_stream):
            self.uber_compose = UberCompose(cfg_constants=self.constants)
            self.response = await self.uber_compose.up(
                compose_files=self.compose_files,
                config_template=Environment(Service('s1'), description='env-a'),
            )
        self.stdout_logs = self.stdout_stream.getvalue()
        self.file_logs = self.log_path.read_text()

    async def then_up_should_finish_successfully(self):
        assert self.response.env_id == schema.str

    async def then_startup_and_migration_stages_should_be_written_to_file(self):
        assert 'Use compose files:' in self.file_logs
        assert 'Generating compose environment files' in self.file_logs
        assert "Starting services pack: ['s1']" in self.file_logs
        assert "Starting compose services ['s1']" in self.file_logs
        assert "Running before-start migrations for ['s1']" in self.file_logs
        assert "Running after-start migrations for ['s1']" in self.file_logs
        assert "Running after-healthy migrations for ['s1']" in self.file_logs
        assert 'Running before-all migrations' in self.file_logs
        assert 'Running after-all migrations' in self.file_logs
        assert 'Starting services for env default_env_id' in self.file_logs

    async def and_same_stages_should_stay_filtered_from_default_stdout(self):
        assert 'Generating compose environment files' not in self.stdout_logs
        assert "Starting compose services ['s1']" not in self.stdout_logs
        assert 'Running before-start migrations' not in self.stdout_logs
