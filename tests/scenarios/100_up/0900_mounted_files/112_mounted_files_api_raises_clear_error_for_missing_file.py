from contexts.compose_file import compose_file
from contexts.isolated_project import isolated_constants
from contexts.isolated_project import isolated_project
from contexts.mounted_file import mounted_template
from contexts.no_docker_containers import no_docker_containers
import vedro
from vedro import catched

from uber_compose import Environment
from uber_compose import MountedFileNotFoundError
from uber_compose import Service
from uber_compose.helpers.current_env import reset_current_env_id
from uber_compose.helpers.current_env import set_current_env_id
from uber_compose.uber_compose import TheUberCompose
from uber_compose.uber_compose import UberCompose


class Scenario(vedro.Scenario):
    subject = 'mounted files API raises clear error for missing file'

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

    async def given_env_with_mounted_file(self):
        self.template_path = mounted_template('env: [[env_id]]\n')
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
        self.client = TheUberCompose(cfg_constants=self.constants)

    async def when_user_requests_missing_mounted_file(self):
        with catched(MountedFileNotFoundError) as self.exc_info:
            self.client.mounted_file_path('missing.yaml')

    async def then_it_should_explain_what_was_requested(self):
        message = str(self.exc_info.value)
        assert "Mounted file not found: 'missing.yaml'" in message
        assert 'file does not exist' in message

    async def and_it_should_show_env_and_searched_path(self):
        message = str(self.exc_info.value)
        searched_path = (
            self.client.mounted_files_dir() / self.response.env_id / 'missing.yaml'
        )
        assert f'Env: {self.response.env_id}' in message
        assert f'Searched in test container: {searched_path}' in message
        assert f'Mounted files root in container: {self.client.mounted_files_dir()}' in message
        assert f'Container project root: {self.constants.in_docker_project_root_path}' in message
        assert 'Hint:' in message
