from uuid import uuid4

from contexts.compose_file import compose_file
from contexts.no_docker_compose_files import no_docker_compose_files
from contexts.no_docker_containers import no_docker_containers
from contexts.no_docker_containers import retrieve_all_docker_containers
from d42 import schema
from helpers.docker_migration_result import get_file_from_container
from rtry import retry
from schemas.docker import ContainerSchema
import vedro

from uber_compose import Environment
from uber_compose import Service
from uber_compose.env_description.env_tools import singleton
from uber_compose.env_description.env_types import Env
from uber_compose.helpers.labels import Label
from uber_compose.uber_compose import UberCompose


class Scenario(vedro.Scenario):
    subject = (
        'singleton service migrations run exactly once across many subsequent reups, '
        'even though each reup recreates the rest of the environment'
    )

    async def given_no_docker_containers(self):
        no_docker_containers()

    async def given_no_docker_compose_files(self):
        no_docker_compose_files()

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

    async def given_env_with_singleton_up_1(self):
        self.release_1 = str(uuid4())
        await UberCompose().up(
            compose_files='docker-compose.yaml',
            config_template=Environment(
                singleton(Service('db')),
                Service('app'),
            ),
            release_id=self.release_1,
        )

    @retry(attempts=3, delay=1)
    async def given_singleton_migration_applied_once(self):
        self.migration_log_before = get_file_from_container('db', self.migration_result_file)
        assert self.migration_log_before == schema.bytes % b'db migration done\n'

    async def given_singleton_container_id_captured(self):
        self.db_container_id_before = [
            container['Id']
            for container in retrieve_all_docker_containers()
            if container['Labels']['com.docker.compose.service'] == 'db'
        ][0]

    async def given_env_with_singleton_up_2_with_app_env_changed(self):
        await UberCompose().up(
            compose_files='docker-compose.yaml',
            config_template=Environment(
                singleton(Service('db')),
                Service('app', Env({'A': '1'})),
            ),
            release_id=str(uuid4()),
        )

    async def when_user_up_env_with_singleton_up_3_with_app_env_changed_again(self):
        self.release_3 = str(uuid4())
        await UberCompose().up(
            compose_files='docker-compose.yaml',
            config_template=Environment(
                singleton(Service('db')),
                Service('app', Env({'A': '2'})),
            ),
            release_id=self.release_3,
        )

    async def then_app_should_be_recreated_with_new_release(self):
        self.containers = retrieve_all_docker_containers()
        assert self.containers == schema.list([
            ...,
            ContainerSchema % {
                'Labels': {
                    'com.docker.compose.service': 'app',
                    Label.RELEASE_ID: self.release_3,
                },
            },
            ...,
        ])

    async def then_singleton_container_identity_should_never_change(self):
        assert self.containers == schema.list([
            ...,
            ContainerSchema % {
                'Id': self.db_container_id_before,
                'Labels': {
                    'com.docker.compose.service': 'db',
                    Label.RELEASE_ID: self.release_1,
                },
            },
            ...,
        ])

    async def then_singleton_migration_should_have_run_exactly_once_in_total(self):
        self.migration_log_final = get_file_from_container('db', self.migration_result_file)
        assert self.migration_log_final == self.migration_log_before
