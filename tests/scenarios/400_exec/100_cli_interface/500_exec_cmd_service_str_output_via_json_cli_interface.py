import vedro
from d42 import schema

from contexts.compose_file import compose_file
from contexts.no_docker_compose_files import no_docker_compose_files
from contexts.no_docker_containers import no_docker_containers
from contexts.services_started import services_started
from uber_compose import CommandResult
from uber_compose import CommonJsonCli
from uber_compose import Environment
from uber_compose import Service


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

    async def given_command(self):
        self.cmd = f'echo "Hello, World! $AAA"'
        self.env = {'AAA': '1'}

    async def when_user_exec_service_cmd(self):
        self.response = await CommonJsonCli().exec(
            container='s1',
            command=self.cmd,
            extra_env=self.env,
        )

    async def then_it_should_exec_command_with_output(self):
        self.expected_log_line = 'Hello, World! 1'
        assert isinstance(self.response, CommandResult)
        assert self.response.stdout == schema.list % [self.expected_log_line]
        assert self.response.stderr == schema.list % [self.expected_log_line ]
