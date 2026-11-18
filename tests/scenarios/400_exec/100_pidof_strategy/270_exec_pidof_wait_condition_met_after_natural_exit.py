from time import sleep

from contexts.compose_file import compose_file
from contexts.isolated_project import isolated_constants
from contexts.isolated_project import isolated_project
from contexts.no_docker_containers import no_docker_containers
from contexts.services_started import services_started
from d42 import schema
import vedro

from uber_compose import Environment
from uber_compose import PidofExecStrategy
from uber_compose import Service
from uber_compose.helpers.exec_result import ExecResult
from uber_compose.uber_compose import UberCompose


class Scenario(vedro.Scenario):
    subject = 'exec with pidof strategy and wait condition met after natural exit'

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
    command: 'sh -c "trap : TERM INT; sleep 604800; wait"'
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

    async def when_user_exec_cmd_with_wait_condition(self):
        self.response = await UberCompose(cfg_constants=self.constants, ).exec(
            container='s1',
            command='sh -c "sleep 1; exit 7"',
            env_id=self.started_services.env_id,
            wait=lambda *_: sleep(2) or True,
            exec=PidofExecStrategy,
        )

    async def then_result_should_be_checked(self):
        assert isinstance(self.response, ExecResult)
        assert self.response.stdout == schema.bytes(b'')
        assert self.response.exit_code is None
