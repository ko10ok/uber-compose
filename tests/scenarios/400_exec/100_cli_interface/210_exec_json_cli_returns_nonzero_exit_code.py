import json

from contexts.compose_file import compose_file
from contexts.isolated_project import isolated_constants
from contexts.isolated_project import isolated_project
from contexts.no_docker_containers import no_docker_containers
from contexts.services_started import services_started
from d42 import schema
import vedro

from uber_compose import CommandResult
from uber_compose import CommonJsonCli
from uber_compose import Environment
from uber_compose import Service
from uber_compose.uber_compose import UberCompose


class Scenario(vedro.Scenario):
    subject = 'exec through CommonJsonCli returns nonzero exit code'

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

    async def given_command(self):
        self.cmd = "sh -c 'echo {\\\"level\\\": \\\"stdout\\\", \\\"A\\\": 1}; exit 7'"

    async def when_user_exec_service_cmd(self):
        self.response = await CommonJsonCli(cli_client=UberCompose(cfg_constants=self.constants, )).exec(
            container='s1',
            command=self.cmd,
        )

    async def then_it_should_return_output_and_exit_code(self):
        self.expected_log_line = json.dumps({"level": "stdout", "A": 1})
        assert isinstance(self.response, CommandResult)
        assert self.response.stdout == schema.list % [self.expected_log_line]
        assert self.response.stderr == schema.list.len(0)
        assert self.response.exit_code == 7
