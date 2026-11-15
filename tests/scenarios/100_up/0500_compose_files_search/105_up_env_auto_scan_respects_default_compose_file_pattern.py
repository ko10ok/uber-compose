from contexts.compose_file import compose_file
from contexts.isolated_project import isolated_constants
from contexts.isolated_project import isolated_project
from contexts.no_docker_containers import no_docker_containers
from contexts.no_docker_containers import retrieve_all_docker_containers
from d42 import schema
from schemas.docker import ContainerSchema
import vedro

from uber_compose.uber_compose import UberCompose


class Scenario(vedro.Scenario):
    subject = 'up env auto scans only files matching default compose file pattern'

    async def given_no_docker_containers(self):
        no_docker_containers()

    async def given_isolated_project(self):
        self.project = isolated_project()
        self.constants = isolated_constants(
            self.project,
            docker_compose_files_scan_depth=3,
        )

    async def given_compose_files_with_matching_and_foreign_names(self):
        self.matching_services = {
            'docker-compose.yaml': 's1',
            'docker-compose.dev.yml': 's2',
            'docker-compose.override.yaml': 's3',
            'services/api/docker-compose.yaml': 's4',
        }
        for filename, service in self.matching_services.items():
            compose_file(filename, content=self._compose_content(service))

        self.foreign_services = {
            'compose.yaml': 'foreign-plain',
            'my-docker-compose.yaml': 'foreign-prefixed',
            'services/api/compose.yaml': 'foreign-nested-plain',
        }
        for filename, service in self.foreign_services.items():
            compose_file(filename, content=self._compose_content(service))

    async def when_user_up_env_without_compose_files(self):
        self.response = await UberCompose(
            cfg_constants=self.constants,
        ).up()

    async def then_only_matching_compose_services_should_be_started(self):
        self.containers = retrieve_all_docker_containers()
        assert self.containers == schema.list.len(4)
        for service in self.matching_services.values():
            assert self.containers == schema.list([
                ...,
                ContainerSchema % {
                    'Labels': {
                        'com.docker.compose.service': service,
                    },
                },
                ...,
            ])

    @staticmethod
    def _compose_content(service: str) -> str:
        return f"""
version: "3"

services:
  {service}:
    image: busybox:stable
    command: 'sh -c "trap : TERM INT; sleep 604800; wait"'
"""
