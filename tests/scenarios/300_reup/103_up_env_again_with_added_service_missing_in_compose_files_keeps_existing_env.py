from contexts.compose_file import compose_file
from contexts.isolated_project import isolated_constants
from contexts.isolated_project import isolated_project
from contexts.no_docker_containers import no_docker_containers
from contexts.no_docker_containers import retrieve_all_docker_containers
from contexts.services_started import services_started
from d42 import schema
from helpers.docker_container import get_container_by_service
from schemas.docker import ContainerSchema
import vedro
from vedro import catched

from uber_compose import Environment
from uber_compose import Service
from uber_compose.errors.up import ServicesUpError
from uber_compose.uber_compose import UberCompose


class Scenario(vedro.Scenario):
    subject = 'up env again with added service missing in compose files keeps existing env'

    async def given_no_docker_containers(self):
        no_docker_containers()

    async def given_isolated_project(self):
        self.project = isolated_project()
        self.constants = isolated_constants(self.project)

    async def given_compose_file_with_s1(self):
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

    async def given_env_with_s1_is_up(self):
        self.environment = Environment(Service('s1'))
        await services_started(
            constants=self.constants,
            compose_files=self.compose_files,
            config_template=self.environment,
        )
        containers_before = retrieve_all_docker_containers()
        self.s1_before = get_container_by_service('s1', containers=containers_before)

    async def given_env_with_added_service_missing_in_compose_files(self):
        self.changed_environment = Environment(
            Service('s1'),
            Service('missing-in-compose'),
        )

    async def when_user_ups_env_again_with_added_missing_service(self):
        with catched(ServicesUpError) as self.exc_info:
            await UberCompose(
                cfg_constants=self.constants,
            ).up(
                compose_files=self.compose_files,
                config_template=self.changed_environment,
            )

    async def then_it_should_fail_with_missing_service_name(self):
        assert self.exc_info.value is not None
        assert 'missing-in-compose' in str(self.exc_info.value)

    async def then_existing_env_should_stay_untouched(self):
        self.containers_after = retrieve_all_docker_containers()
        assert self.containers_after == schema.list.len(1)
        assert self.containers_after == schema.list([
            ...,
            ContainerSchema % {
                'Id': self.s1_before['Id'],
                'State': self.s1_before['State'],
                'Labels': {
                    'com.docker.compose.service': 's1',
                },
            },
            ...,
        ])
