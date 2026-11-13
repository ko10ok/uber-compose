from contextlib import redirect_stdout
from io import StringIO

from contexts.compose_file import compose_file
from contexts.isolated_project import isolated_constants
from contexts.isolated_project import isolated_project
from contexts.no_docker_containers import no_docker_containers
import vedro

from uber_compose.env_description.env_types import Environment
from uber_compose.env_description.env_types import Service
from uber_compose.uber_compose import UberCompose


class Scenario(vedro.Scenario):
    subject = 'up env default logs keep only high level stages'

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

    async def when_user_up_env_with_default_log_policy(self):
        self.log_stream = StringIO()
        with redirect_stdout(self.log_stream):
            self.uber_compose = UberCompose(cfg_constants=self.constants)
            self.response = await self.uber_compose.up(
                compose_files=self.compose_files,
                config_template=Environment(Service('s1'), description='env-a'),
            )
        self.logs = self.log_stream.getvalue()

    async def then_high_level_stages_should_be_visible(self):
        assert 'Starting new env-a environment' in self.logs
        assert 'Starting services check up' in self.logs
        assert '✔ All services up' in self.logs

    async def and_stage_completion_should_have_the_same_level(self):
        assert ' ✔ Starting new env-a environment (' in self.logs

    async def and_substep_stages_should_not_be_visible(self):
        assert 'Generating compose environment files' not in self.logs
        assert 'Running before-all migrations' not in self.logs
        assert 'Starting services pack:' not in self.logs
        assert 'Starting compose services' not in self.logs
        assert 'Running migration:' not in self.logs
        assert 'Waiting for services to become healthy' not in self.logs
        assert 'Starting services for env default_env_id' not in self.logs
