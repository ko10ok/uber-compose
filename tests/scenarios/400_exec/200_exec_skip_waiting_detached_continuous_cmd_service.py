import vedro
from d42 import schema

from contexts.compose_file import compose_file
from contexts.no_docker_compose_files import no_docker_compose_files
from contexts.no_docker_containers import no_docker_containers
from contexts.services_started import services_started
from uber_compose import Environment
from uber_compose import Service
from uber_compose.helpers.exec_result import ExecResult
from uber_compose.uber_compose import UberCompose
from uber_compose.helpers.bytes_pickle import debase64_pickled
from schemas.http_codes import HTTPStatusCodeOk
from uber_compose.output.console import LogPolicy


class Scenario(vedro.Scenario):
    async def no_docker_containers(self):
        no_docker_containers()

    async def no_docker_copose_files(self):
        no_docker_compose_files()

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
            compose_files=self.compose_filename,
            config_template=Environment(
                Service('s1')
            )
        )

    async def when_user_exec_service_cmd(self):
        self.response = await UberCompose().exec(
            container='s1',
            command='sh -c "sleep 100 && echo \\"Hello, World!\\""',
            env_id=self.started_services.env_id,
            wait=None,
        )

    async def then_it_should_exec_command_with_output(self):
        assert isinstance(self.response, ExecResult)
        assert self.response.stdout == schema.bytes(b'')
