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
    subject = 'up env mounting same template to multiple targets'

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
        self.target_a = '/app/config-a.yaml'
        self.target_b = '/app/config-b.yaml'

    async def given_env_with_same_template_for_two_targets(self):
        self.environment = Environment(
            Service(
                's1',
                mounted_files=(
                    f'{self.template_path}:{self.target_a}',
                    f'{self.template_path}:{self.target_b}',
                ),
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

    async def then_both_targets_should_contain_rendered_content(self):
        expected = b'env: default_env_id\nservice: s1\n'
        assert get_file_from_container('s1', self.target_a) == expected
        assert get_file_from_container('s1', self.target_b) == expected

    async def and_container_should_have_mounts_for_both_targets(self):
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
                        'Destination': self.target_a,
                    },
                    {
                        'Source': str(rendered_source),
                        'Destination': self.target_b,
                    },
                ],
            },
            ...,
        ])
