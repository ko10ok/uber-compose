from uuid import uuid4

from contexts.compose_file import compose_file
from contexts.isolated_project import isolated_constants
from contexts.isolated_project import isolated_project
from contexts.no_docker_containers import no_docker_containers
from contexts.no_docker_containers import retrieve_all_docker_containers
from d42 import schema
from helpers.docker_migration_result import get_file_from_container
from rtry import retry
from schemas.docker import ContainerSchema
import vedro
from vedro import catched

from uber_compose import Environment
from uber_compose import Service
from uber_compose.env_description.env_tools import singleton
from uber_compose.env_description.env_types import Env
from uber_compose.errors.up import SingletonConfigChangedError
from uber_compose.uber_compose import UberCompose


class Scenario(vedro.Scenario):
    subject = 'up with changed singleton config raises error and keeps running environment untouched'

    async def given_no_docker_containers(self):
        no_docker_containers()

    async def given_isolated_project(self):
        self.project = isolated_project()
        self.instance_files_root = self.project.tmp_envs_path
        self.constants = isolated_constants(self.project)

    async def given_compose_files(self):
        self.migration_result_file = '/tmp/migration.log'
        compose_file(
            'docker-compose.yaml',
            content="""
version: "3"

services:
  db:
    image: busybox:stable
    command: 'sh -c "trap : TERM INT; sleep 604800; wait"'
    x-migration:
      - after_start: sh -c 'echo "db migration done" >> /tmp/migration.log'

  app:
    image: busybox:stable
    command: 'sh -c "trap : TERM INT; sleep 604800; wait"'
"""
        )

    async def given_env_with_singleton_up(self):
        self.start_release = str(uuid4())
        await UberCompose(cfg_constants=self.constants, ).up(
            compose_files='docker-compose.yaml',
            config_template=Environment(
                singleton(Service('db', Env({'SINGLETON_MODE': 'a'}))),
                Service('app'),
            ),
            release_id=self.start_release,
        )

    @retry(attempts=3, delay=1)
    async def given_singleton_migration_applied_once(self):
        self.migration_log_before = get_file_from_container('db', self.migration_result_file)
        assert self.migration_log_before == schema.bytes % b'db migration done\n'

    async def given_running_containers_captured(self):
        self.containers_before = sorted(
            retrieve_all_docker_containers(),
            key=lambda container: container['Id'],
        )

    async def when_user_up_env_again_with_changed_singleton_config(self):
        self.next_release = str(uuid4())
        with catched(SingletonConfigChangedError) as self.exc_info:
            await UberCompose(cfg_constants=self.constants, ).up(
                compose_files='docker-compose.yaml',
                config_template=Environment(
                    singleton(Service('db', Env({'SINGLETON_MODE': 'b'}))),
                    Service('app'),
                ),
                release_id=self.next_release,
            )

    async def then_it_should_raise_singleton_config_changed_error(self):
        assert self.exc_info.type is SingletonConfigChangedError
        assert 'db' in str(self.exc_info.value)
        assert 'must not change' in str(self.exc_info.value)

    async def then_running_containers_should_not_be_changed(self):
        self.containers_after = sorted(
            retrieve_all_docker_containers(),
            key=lambda container: container['Id'],
        )
        assert self.containers_after == schema.list([
            ContainerSchema % {
                'Id': container['Id'],
            }
            for container in self.containers_before
        ])

    async def then_singleton_migration_should_not_be_rerun(self):
        self.migration_log_after = get_file_from_container('db', self.migration_result_file)
        assert self.migration_log_after == self.migration_log_before
