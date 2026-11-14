from pathlib import Path

from helpers.env_vars import patch_env
import vedro

from uber_compose.core.constants import Constants


class Scenario(vedro.Scenario):
    subject = 'resolve relative mounted files directory from host project root'

    async def given_mounted_files_directory_is_relative(self):
        patch_env({
            'COMPOSE_PROJECT_NAME': 'uc-mounted-files-unit',
            'HOST_PROJECT_ROOT_DIRECTORY': '/host/project',
            'MOUNTED_FILES_DIRECTORY': 'e2e-neo/e2e_mounted_files',
        })

    async def when_constants_are_created(self):
        self.constants = Constants()

    async def then_mounted_files_path_should_be_resolved_from_container_project_root(self):
        assert self.constants.mounted_files_path == Path(
            '/project/e2e-neo/e2e_mounted_files'
        )

    async def and_mounted_files_host_path_should_be_resolved_from_host_project_root(self):
        assert self.constants.mounted_files_host_path == Path(
            '/host/project/e2e-neo/e2e_mounted_files'
        )
