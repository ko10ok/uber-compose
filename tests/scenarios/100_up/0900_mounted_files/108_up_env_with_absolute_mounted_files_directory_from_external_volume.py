from contexts.compose_file import compose_file
from contexts.isolated_project import isolated_constants
from contexts.isolated_project import isolated_project
from contexts.mounted_file import mounted_template
from contexts.no_docker_containers import no_docker_containers
from contexts.no_docker_containers import retrieve_all_docker_containers
from d42 import schema
from schemas.docker import ContainerSchema
import vedro

from uber_compose import Environment
from uber_compose import Service
from uber_compose.uber_compose import UberCompose


class Scenario(vedro.Scenario):
    subject = 'up env with absolute mounted files directory from external volume'

    async def given_no_docker_containers(self):
        no_docker_containers()

    async def given_isolated_project(self):
        self.project = isolated_project()
        self.absolute_mounted_files_path = (
            self.project.tmp_envs_path / 'absolute-mounted-files'
        )
        self.constants = isolated_constants(
            self.project,
            mounted_files_path=self.absolute_mounted_files_path,
        )

    async def given_compose_file(self):
        self.compose_files = 'docker-compose.yaml'
        compose_file(
            self.compose_files,
            content="""
version: "3"

services:
  s1:
    image: busybox:stable
    command: 'sh -c "trap : TERM INT; sleep 604800; wait"'
"""
        )

    async def given_mounted_template(self):
        self.template_path = mounted_template(
            'env: [[env_id]]\nservice: [[s1]]\n'
        )
        self.target_path = '/app/config.yaml'

    async def given_env_with_mounted_file(self):
        self.environment = Environment(
            Service(
                's1',
                mounted_files=(f'{self.template_path}:{self.target_path}',),
            ),
            description='env-a',
        )

    async def when_user_up_env(self):
        self.response = await UberCompose(
            cfg_constants=self.constants,
        ).up(
            compose_files=self.compose_files,
            config_template=self.environment,
        )

    async def then_absolute_directory_should_be_used_for_write_and_mount(self):
        assert self.constants.mounted_files_path == self.absolute_mounted_files_path
        assert self.constants.mounted_files_host_path == self.absolute_mounted_files_path

    async def and_mounted_file_should_be_rendered_into_absolute_directory(self):
        rendered_source = (
            self.absolute_mounted_files_path
            / self.response.env_id
            / self.template_path
        )
        assert rendered_source.read_text() == 'env: default_env_id\nservice: s1\n'

    async def and_container_should_mount_file_from_absolute_directory(self):
        absolute_source = (
            self.absolute_mounted_files_path
            / self.response.env_id
            / self.template_path
        )
        assert retrieve_all_docker_containers() == schema.list([
            ...,
            ContainerSchema % {
                'Mounts': [
                    {
                        'Source': str(absolute_source),
                        'Destination': self.target_path,
                    },
                ],
            },
            ...,
        ])
