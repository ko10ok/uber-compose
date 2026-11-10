from contexts.compose_file import compose_file
from contexts.isolated_project import isolated_constants
from contexts.isolated_project import isolated_project
from contexts.no_docker_containers import no_docker_containers
import vedro
from vedro import catched

from uber_compose.uber_compose import TheUberCompose


class Scenario(vedro.Scenario):
    subject = 'mounted files API rejects absolute path'

    async def given_no_docker_containers(self):
        no_docker_containers()

    async def given_isolated_project(self):
        self.project = isolated_project()
        self.constants = isolated_constants(self.project)

    async def given_compose_file(self):
        compose_file(
            'docker-compose.yaml',
            content="""
version: "3"

services:
  s1:
    image: busybox:stable
    command: 'sh -c "trap : TERM INT; sleep 604800; wait"'
"""
        )

    async def given_client(self):
        self.client = TheUberCompose(cfg_constants=self.constants)

    async def when_user_requests_absolute_mounted_file_path(self):
        with catched(ValueError) as self.exc_info:
            self.client.mounted_file_path('/tmp/missing.yaml')

    async def then_it_should_explain_that_path_must_be_relative(self):
        message = str(self.exc_info.value)
        assert 'expects a relative path' in message
        assert '/tmp/missing.yaml' in message
