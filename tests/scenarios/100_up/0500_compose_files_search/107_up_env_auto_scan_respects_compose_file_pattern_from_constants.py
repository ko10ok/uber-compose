from contexts.compose_file import compose_file
from contexts.isolated_project import isolated_constants
from contexts.isolated_project import isolated_project
from contexts.no_docker_containers import no_docker_containers
from contexts.no_docker_containers import retrieve_all_docker_containers
from d42 import schema
from schemas.docker import ContainerSchema
import vedro

from uber_compose.helpers.labels import Label
from uber_compose.uber_compose import UberCompose


class Scenario(vedro.Scenario):
    subject = 'up env auto scan matches compose file pattern against full relative path from constants'

    async def given_no_docker_containers(self):
        no_docker_containers()

    async def given_isolated_project_with_custom_pattern(self):
        self.project = isolated_project()
        self.constants = isolated_constants(
            self.project,
            docker_compose_files_scan_depth=3,
            docker_compose_files_auto_scan_pattern=r'^services/api/custom-compose\.ya?ml$',
        )

    async def given_compose_files_with_default_and_custom_names(self):
        self.compose_files = [
            'docker-compose.yaml',
            'custom-compose.yaml',
            'services/api/docker-compose.yaml',
            'services/api/custom-compose.yaml',
            'other/custom-compose.yaml',
        ]
        for index, filename in enumerate(self.compose_files):
            compose_file(filename, content=self._compose_content(f'service-{index}'))

    async def when_user_up_env_without_compose_files(self):
        self.response = await UberCompose(
            cfg_constants=self.constants,
        ).up()

    async def then_only_service_from_matching_path_should_be_started(self):
        assert retrieve_all_docker_containers() == schema.list([
            ContainerSchema % {
                'Labels': {
                    'com.docker.compose.service': 'service-3',
                    Label.COMPOSE_FILES: 'services/api/custom-compose.yaml',
                },
            },
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
