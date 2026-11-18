import asyncio

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
from uber_compose import ExecLifeCyclePolicy
from uber_compose import Service
from uber_compose.uber_compose import UberCompose


class Scenario(vedro.Scenario):
    subject = 'exec command with trailing ampersand'

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

    async def when_user_exec_background_cmd(self):
        self.command = 'tail -f /dev/null &'
        self.response = await CommonJsonCli(cli_client=UberCompose(cfg_constants=self.constants, )).exec(
            container='s1',
            command=self.command,
            env_id=self.started_services.env_id,
            life_cycle_policy=ExecLifeCyclePolicy(
                kill_after_command_still_running=False,
            ),
        )

    async def then_result_should_be_checked(self):
        assert isinstance(self.response, CommandResult)
        assert self.response.stdout == schema.list.len(0)
        assert self.response.stderr == schema.list.len(0)
        assert self.response.cmd == self.command
        assert self.response.env == {}
        assert self.response.exit_code is None
        assert self.response.waiting_done_successfully is True

    async def then_has_no_errors_should_raise(self):
        self.exception = None
        try:
            assert self.response.has_no_errors()
        except AssertionError as e:
            self.exception = e

        assert isinstance(self.exception, AssertionError)

    async def then_process_should_be_checked(self):
        await asyncio.sleep(0.5)
        self.process_check = await UberCompose(cfg_constants=self.constants, ).exec(
            container='s1',
            command='pidof tail',
            env_id=self.started_services.env_id,
        )
        assert self.process_check.stdout
