from pathlib import Path

from contexts.compose_file import compose_file
from contexts.isolated_project import isolated_constants
from contexts.isolated_project import isolated_project
from contexts.mounted_file import mounted_template
from contexts.no_docker_containers import no_docker_containers
from contexts.no_docker_containers import retrieve_all_docker_containers
from d42 import schema
from helpers.docker_migration_result import get_file_from_container
from schemas.docker import ContainerSchema
import vedro

from uber_compose import Environment
from uber_compose import Service
from uber_compose.uber_compose import UberCompose


class Scenario(vedro.Scenario):
    subject = 'up env with mounted file at default target'

    async def given_no_docker_containers(self):
        no_docker_containers()

    async def given_isolated_project(self):
        self.project = isolated_project()
        self.instance_files_root = self.project.tmp_envs_path
        self.constants = isolated_constants(self.project)

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
        self.target_path = f'/e2e_mounted_files/{Path(self.template_path).as_posix()}'

    async def given_env_with_mounted_file(self):
        self.environment = Environment(
            Service('s1', mounted_files=(self.template_path,)),
            description='env-a',
        )

    async def when_user_up_env(self):
        self.response = await UberCompose(
            cfg_constants=self.constants,
        ).up(
            compose_files=self.compose_files,
            config_template=self.environment,
        )

    async def then_mounted_file_should_be_rendered_to_default_target(self):
        content = get_file_from_container('s1', self.target_path)
        assert content == b'env: default_env_id\nservice: s1\n'

    async def and_container_should_have_mount_from_rendered_file(self):
        rendered_source = (
            Path.cwd() / 'e2e_mounted_files' / self.response.env_id / self.template_path
        )
        self.containers = retrieve_all_docker_containers()
        assert self.containers == schema.list([
            ...,
            ContainerSchema % {
                'Mounts': [
                    {
                        'Source': str(rendered_source),
                        'Destination': self.target_path,
                    },
                ],
            },
            ...,
        ])
