from contexts.compose_file import compose_file
from contexts.isolated_project import isolated_constants
from contexts.isolated_project import isolated_project
from contexts.no_docker_containers import no_docker_containers
from contexts.services_started import services_started
import vedro

from uber_compose import Environment
from uber_compose import Service
from uber_compose import TimeOutCheck
from uber_compose.helpers.exec_result import ExecTimeout
from uber_compose.uber_compose import UberCompose


class Scenario(vedro.Scenario):
    subject = 'exec with process exit wait returns timeout when command is still running'

    async def given_no_docker_containers(self):
        no_docker_containers()

    async def given_isolated_project(self):
        self.project = isolated_project()
        self.constants = isolated_constants(self.project)

    async def given_compose_files(self):
        self.compose_filename = compose_file(
            'docker-compose.yaml',
            content="""
version: "3"

services:
  s1:
    image: busybox:stable
    command: 'sh -c "trap : TERM INT; sleep 604800 & wait"'
"""
        )

    async def given_service_started(self):
        self.started_services = await services_started(
            constants=self.constants,
            compose_files=self.compose_filename,
            config_template=Environment(
                Service('s1')
            )
        )

    async def when_user_exec_long_running_cmd(self):
        self.response = await UberCompose(cfg_constants=self.constants, ).exec(
            container='s1',
            command='tail -f /dev/null',
            env_id=self.started_services.env_id,
            timeout=TimeOutCheck(attempts=1, delay_s=1),
        )

    async def then_it_should_return_timeout_without_exit_code(self):
        assert isinstance(self.response, ExecTimeout)
        assert self.response.exit_code is None
