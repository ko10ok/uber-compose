from io import StringIO
import re

from contexts.compose_file import compose_file
from contexts.isolated_project import isolated_constants
from contexts.isolated_project import isolated_project
from contexts.no_docker_containers import no_docker_containers
from rich.console import Console
import vedro

from uber_compose.env_description.env_types import Environment
from uber_compose.env_description.env_types import Service
from uber_compose.output.console import LogPolicy
from uber_compose.uber_compose import UberCompose


class Scenario(vedro.Scenario):
    subject = 'up env logs completed stages with timing'

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

    async def when_user_up_env_with_log_capture(self):
        self.log_stream = StringIO()
        self.uber_compose = UberCompose(cfg_constants=self.constants, log_policy=LogPolicy.VERBOSE)
        self.uber_compose.logger.stream = Console(
            file=self.log_stream,
            force_terminal=False,
            soft_wrap=True,
        )
        self.response = await self.uber_compose.up(
            compose_files=self.compose_files,
            config_template=Environment(Service('s1'), description='env-a'),
        )
        self.manual_stage = self.uber_compose.logger.stage('Manual stage')
        self.manual_stage.done()
        self.manual_stage.done()
        self.logs = self.log_stream.getvalue()

    async def when_manual_stage_levels_are_finished(self):
        self.uber_compose.logger.log_policy = LogPolicy.DEBUG
        self.info_stage = self.uber_compose.logger.stage_info('Info stage')
        self.info_stage.done()
        self.debug_stage = self.uber_compose.logger.stage_debug('Debug stage')
        self.debug_stage.done()
        self.leveled_logs = self.log_stream.getvalue()

    async def then_manual_stage_done_should_log_once_with_timing(self):
        assert self.logs.count(' ✔ Manual stage (') == 1
        assert re.search(r' ✔ Manual stage \(\d+\.\d{2}s\)', self.logs)

    async def then_stage_info_and_debug_should_keep_their_log_levels(self):
        assert 'LogEvents.STAGE_INFO:' in self.leveled_logs
        assert 'LogEvents.STAGE_DEBUG:' in self.leveled_logs
        assert re.search(r' ✔ Info stage \(\d+\.\d{2}s\)', self.leveled_logs)
        assert re.search(r' ✔ Debug stage \(\d+\.\d{2}s\)', self.leveled_logs)

    async def then_big_environment_stage_should_be_completed_with_timing(self):
        assert 'Starting new env-a environment' in self.logs
        assert re.search(
            r' ✔ Starting new env-a environment \(\d+\.\d{2}s\)',
            self.logs,
        )

    async def then_compose_files_generation_should_be_completed_with_timing(self):
        assert 'Generating compose environment files' in self.logs
        assert re.search(
            r' ✔ Generating compose environment files \(\d+\.\d{2}s\)',
            self.logs,
        )

    async def then_migration_stages_should_be_completed_with_timing(self):
        assert 'Running before-all migrations' in self.logs
        assert re.search(
            r' ✔ Running before-all migrations \(\d+\.\d{2}s\)',
            self.logs,
        )
        assert "Running before-start migrations for ['s1']" in self.logs
        assert re.search(
            r" ✔ Running before-start migrations for \['s1'\] \(\d+\.\d{2}s\)",
            self.logs,
        )
        assert "Running after-start migrations for ['s1']" in self.logs
        assert re.search(
            r" ✔ Running after-start migrations for \['s1'\] \(\d+\.\d{2}s\)",
            self.logs,
        )
        assert "Running after-healthy migrations for ['s1']" in self.logs
        assert re.search(
            r" ✔ Running after-healthy migrations for \['s1'\] \(\d+\.\d{2}s\)",
            self.logs,
        )
        assert 'Running after-all migrations' in self.logs
        assert re.search(
            r' ✔ Running after-all migrations \(\d+\.\d{2}s\)',
            self.logs,
        )

    async def then_services_pack_stage_should_be_completed_with_timing(self):
        assert "Starting services pack: ['s1']" in self.logs
        assert re.search(
            r" ✔ Starting services pack: \['s1'\] \(\d+\.\d{2}s\)",
            self.logs,
        )

    async def then_compose_services_stage_should_be_completed_with_timing(self):
        assert "Starting compose services ['s1']" in self.logs
        assert re.search(
            r" ✔ Starting compose services \['s1'\] \(\d+\.\d{2}s\)",
            self.logs,
        )

    async def then_health_wait_stages_should_be_completed_with_timing(self):
        assert "Waiting for services to become healthy ['s1']" in self.logs
        assert re.search(
            r" ✔ Waiting for services to become healthy \['s1'\] \(\d+\.\d{2}s\)",
            self.logs,
        )
        assert 'Waiting for all services to become healthy' in self.logs
        assert re.search(
            r' ✔ Waiting for all services to become healthy \(\d+\.\d{2}s\)',
            self.logs,
        )

    async def then_services_start_stage_should_be_completed_with_timing(self):
        assert 'Starting services for env default_env_id' in self.logs
        assert re.search(
            r' ✔ Starting services for env default_env_id \(\d+\.\d{2}s\)',
            self.logs,
        )
        assert self.logs.count(' ✔ ') >= 10
