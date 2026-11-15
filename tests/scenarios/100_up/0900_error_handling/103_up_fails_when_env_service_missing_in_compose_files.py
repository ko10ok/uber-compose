from contexts.compose_file import compose_file
from contexts.isolated_project import isolated_constants
from contexts.isolated_project import isolated_project
from contexts.no_docker_containers import no_docker_containers
from contexts.no_docker_containers import retrieve_all_docker_containers
from d42 import schema
import vedro
from vedro import catched

from uber_compose import Environment
from uber_compose import Service
from uber_compose.errors.up import ServicesUpError
from uber_compose.uber_compose import UberCompose


class Scenario(vedro.Scenario):
    subject = 'up fails when env declares service missing in compose files'

    async def given_no_docker_containers(self):
        no_docker_containers()

    async def given_isolated_project(self):
        self.project = isolated_project()
        self.constants = isolated_constants(self.project)

    async def given_compose_file_with_services(self):
        self.compose_files = 'docker-compose.yaml'
        compose_file(
            self.compose_files,
            content="""
version: "3"

services:
  s1:
    image: busybox:stable
    command: 'sh -c "trap : TERM INT; sleep 604800; wait"'

  s2:
    image: busybox:stable
    command: 'sh -c "trap : TERM INT; sleep 604800; wait"'
""",
        )

    async def given_env_with_service_missing_in_compose_files(self):
        self.environment = Environment(
            Service('s1'),
            Service('missing-in-compose'),
        )

    async def when_user_up_env_with_missing_service(self):
        with catched(ServicesUpError) as self.exc_info:
            await UberCompose(
                cfg_constants=self.constants,
            ).up(
                compose_files=self.compose_files,
                config_template=self.environment,
            )

    async def then_it_should_fail_with_missing_service_name(self):
        assert self.exc_info.value is not None
        assert 'missing-in-compose' in str(self.exc_info.value)

    async def then_it_should_not_start_any_containers(self):
        assert retrieve_all_docker_containers() == schema.list([])
