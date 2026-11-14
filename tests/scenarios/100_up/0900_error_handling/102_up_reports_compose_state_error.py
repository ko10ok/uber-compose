from contexts.compose_file import compose_file
from contexts.isolated_project import isolated_constants
from contexts.isolated_project import isolated_project
from contexts.no_docker_containers import no_docker_containers
import vedro
from vedro import catched

from uber_compose import Environment
from uber_compose import Service
from uber_compose.uber_compose import UberCompose


class Scenario(vedro.Scenario):
    subject = 'up reports compose state error when compose CLI fails'

    async def given_no_docker_containers(self):
        no_docker_containers()

    async def given_isolated_project(self):
        self.project = isolated_project()

    async def given_compose_file_with_service(self):
        self.compose_files = 'docker-compose.yaml'
        compose_file(
            self.compose_files,
            content="""
version: "3"

services:
  s1:
    image: busybox:stable
    command: 'sh -c "trap : TERM INT; sleep 604800; wait"'
""",
        )

    async def given_broken_compose_cli(self):
        self.broken_compose_cli = self.project.project_root / 'broken-compose.sh'
        self.broken_compose_cli.write_text(
            '#!/bin/sh\n'
            'echo "compose state failed" >&2\n'
            'exit 1\n'
        )
        self.broken_compose_cli.chmod(0o755)
        self.constants = isolated_constants(
            self.project,
            cli_compose_util_override=str(self.broken_compose_cli),
        )

    async def when_user_ups_environment(self):
        with catched(Exception) as self.exc_info:
            await UberCompose(cfg_constants=self.constants).up(
                compose_files=self.compose_files,
                config_template=Environment(Service('s1')),
            )

    async def then_error_should_contain_compose_cli_output(self):
        assert 'compose state failed' in str(self.exc_info.value)
