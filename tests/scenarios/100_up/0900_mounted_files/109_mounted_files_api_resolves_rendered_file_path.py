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
    subject = 'mounted files API resolves rendered file path for current env'

    async def given_no_docker_containers(self):
        no_docker_containers()

    async def given_isolated_project(self):
        self.project = isolated_project()
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

    async def then_api_should_return_rendered_file_path(self):
        self.client = TheUberCompose(cfg_constants=self.constants)
        expected_path = (
            self.client.mounted_files_dir() / self.response.env_id / self.template_path
        )
        assert self.client.mounted_file_path(self.template_path) == expected_path

    async def and_rendered_file_should_exist_with_rendered_content(self):
        rendered_file = self.client.mounted_file_path(self.template_path)
        assert rendered_file.read_text() == f'env: {self.response.env_id}\nservice: s1-{self.response.env_id}\n'
