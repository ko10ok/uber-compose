from contexts.compose_file import compose_file
from contexts.isolated_project import isolated_constants
from contexts.isolated_project import isolated_project
from contexts.no_docker_containers import no_docker_containers
import vedro
from vedro import catched

from uber_compose import MountedFileNotFoundError
from uber_compose.helpers.current_env import reset_current_env_id
from uber_compose.helpers.current_env import set_current_env_id
from uber_compose.uber_compose import TheUberCompose


class Scenario(vedro.Scenario):
    subject = 'mounted files API raises clear error when env mounted directory is missing'

    async def given_no_docker_containers(self):
        no_docker_containers()

    async def given_isolated_project(self):
        self.project = isolated_project()
        self.constants = isolated_constants(self.project)

    async def given_compose_file(self):
        compose_file(
            'docker-compose.yaml',
            content="""
version: "3"

services:
  s1:
    image: busybox:stable
    command: 'sh -c "trap : TERM INT; sleep 604800; wait"'
"""
        )

    async def given_current_env_without_mounted_files(self):
        vedro.defer(reset_current_env_id)
        set_current_env_id('w9-missing')
        self.client = TheUberCompose(cfg_constants=self.constants)

    async def when_user_requests_missing_mounted_file(self):
        with catched(MountedFileNotFoundError) as self.exc_info:
            self.client.mounted_file_path('missing.yaml')

    async def then_it_should_show_env_and_searched_path(self):
        searched_path = self.client.mounted_files_dir() / 'w9-missing' / 'missing.yaml'
        message = str(self.exc_info.value)
        assert "Mounted file not found: 'missing.yaml'" in message
        assert 'Env: w9-missing' in message
        assert f'Searched in test container: {searched_path}' in message
        assert f'Mounted files root in container: {self.client.mounted_files_dir()}' in message
        assert f'Container project root: {self.constants.in_docker_project_root_path}' in message
