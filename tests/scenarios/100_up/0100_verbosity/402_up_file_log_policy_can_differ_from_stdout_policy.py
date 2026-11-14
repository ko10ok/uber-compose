from contexts.compose_file import compose_file
from contexts.isolated_project import isolated_constants
from contexts.isolated_project import isolated_project
from contexts.no_docker_containers import no_docker_containers
from d42 import schema
import vedro

from uber_compose.env_description.env_types import Environment
from uber_compose.env_description.env_types import Service
from uber_compose.output.console import LogEvents
from uber_compose.output.console import LogPolicySet
from uber_compose.uber_compose import UberCompose


class Scenario(vedro.Scenario):
    subject = 'up env file log policy can differ from stdout policy'

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

    async def when_user_up_env_with_stage_only_file_policy(self):
        self.response = await UberCompose(
            cfg_constants=self.constants,
            file_log_policy=LogPolicySet(LogEvents.STAGE),
        ).up(
            compose_files=self.compose_files,
            config_template=Environment(Service('s1'), description='env-a'),
        )
        self.file_logs = self.log_path.read_text()

    async def then_up_should_finish_successfully(self):
        assert self.response.env_id == schema.str

    async def then_file_should_contain_only_stage_level_logs(self):
        assert 'Starting new env-a environment' in self.file_logs
        assert 'Generating compose environment files' not in self.file_logs
        assert "Starting compose services ['s1']" not in self.file_logs
        assert 'Running before-start migrations' not in self.file_logs
