from pathlib import Path
import re

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
    subject = 'up env writes logs next to tracing reports under logs/startup by default'

    async def given_no_docker_containers(self):
        no_docker_containers()

    async def given_isolated_project(self):
        self.project = isolated_project()
        self.constants = isolated_constants(self.project)

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

    async def when_user_up_env_without_explicit_log_path(self):
        self.uber_compose = UberCompose(cfg_constants=self.constants)
        self.response = await self.uber_compose.up(
            compose_files=self.compose_files,
            config_template=Environment(Service('s1'), description='env-a'),
        )
        self.log_path = self.uber_compose.logger.log_file_path
        self.file_logs = self.log_path.read_text()

    async def then_up_should_finish_successfully(self):
        assert self.response.env_id == schema.str

    async def then_log_file_should_be_written_to_logs_startup(self):
        assert self.log_path.parent == Path.cwd() / 'logs' / 'startup'
        assert re.fullmatch(r'uber-compose-\d{8}_\d{6}_\d{6}-\d+\.log', self.log_path.name)
        assert self.log_path.exists()
        assert 'Generating compose environment files' in self.file_logs
