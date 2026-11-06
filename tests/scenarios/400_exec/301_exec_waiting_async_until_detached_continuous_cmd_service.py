from time import sleep

from contexts.compose_file import compose_file
from contexts.isolated_project import isolated_constants
from contexts.isolated_project import isolated_project
from contexts.no_docker_containers import no_docker_containers
from contexts.services_started import services_started
from d42 import schema
import vedro

from uber_compose import Environment
from uber_compose import Service
from uber_compose.helpers.exec_result import ExecResult
from uber_compose.uber_compose import UberCompose


class Scenario(vedro.Scenario):
    async def given_no_docker_containers(self):
        no_docker_containers()

    async def given_isolated_project(self):
        self.project = isolated_project()
        self.instance_files_root = self.project.tmp_envs_path
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

    async def given_wait_fn(self):
        async def fn(*_):
            sleep(3)
            return True
        self.fn = fn

    async def when_user_exec_service_cmd(self):
        self.response = await UberCompose(cfg_constants=self.constants, ).exec(
            container='s1',
            command='sh -c "sleep 1 && echo \\"Hello, World!\\""',
            env_id=self.started_services.env_id,
            wait=self.fn,
        )

    async def then_it_should_exec_command_with_output(self):
        assert isinstance(self.response, ExecResult)
        assert self.response.stdout == schema.bytes(b'Hello, World!\n')
