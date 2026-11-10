from contexts.compose_file import compose_file
from contexts.isolated_project import isolated_constants
from contexts.isolated_project import isolated_project
from contexts.mounted_file import mounted_template
from contexts.no_docker_containers import no_docker_containers
import vedro

from uber_compose import Environment
from uber_compose import Service
from uber_compose.helpers.current_env import reset_current_env_id
from uber_compose.helpers.current_env import set_current_env_id
from uber_compose.uber_compose import TheUberCompose
from uber_compose.uber_compose import UberCompose


class Scenario(vedro.Scenario):
    subject = 'mounted files API resolves relative mounted files directory'

    async def given_no_docker_containers(self):
        no_docker_containers()

    async def given_isolated_project(self):
        self.project = isolated_project()
        self.relative_mounted_files_path = 'e2e-neo/e2e_mounted_files'
        self.expected_mounted_files_path = (
            self.project.project_root / self.relative_mounted_files_path
        )
        self.constants = isolated_constants(
            self.project,
            mounted_files_path=self.relative_mounted_files_path,
            mounted_files_host_path=self.expected_mounted_files_path,
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
        self.template_path = mounted_template('env: [[env_id]]\nservice: [[s1]]\n')

    async def when_user_up_env_with_mounted_file(self):
        self.response = await UberCompose(cfg_constants=self.constants).up(
            compose_files=self.compose_files,
            config_template=Environment(
                Service('s1', mounted_files=(self.template_path,)),
                description='env-a',
            ),
            parallelism_limit=2,
        )
        vedro.defer(reset_current_env_id)
        set_current_env_id(self.response.env_id)

    async def then_api_should_resolve_relative_directory_from_project_root(self):
        self.client = TheUberCompose(cfg_constants=self.constants)
        assert self.client.mounted_files_dir() == self.expected_mounted_files_path

    async def and_api_should_point_to_rendered_file_in_current_env(self):
        rendered_file = self.client.mounted_file_path(self.template_path)
        assert rendered_file == (
            self.expected_mounted_files_path / self.response.env_id / self.template_path
        )
        assert rendered_file.read_text() == (
            f'env: {self.response.env_id}\nservice: s1-{self.response.env_id}\n'
        )
