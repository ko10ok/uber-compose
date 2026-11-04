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
from uber_compose.helpers.labels import Label
from uber_compose.uber_compose import UberCompose


class Scenario(vedro.Scenario):
    subject = (
        'an explicit force_restart=True still restarts a singleton service and reruns its '
        'migrations - singleton protection must not override an explicit user request'
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

    async def given_start_env(self):
        self.start_release = str(uuid4())
        await UberCompose().up(
            compose_files='docker-compose.yaml',
            config_template=Environment(
                singleton(Service('db')),
                Service('app'),
            ),
            release_id=self.start_release,
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

    async def given_next_run_release(self):
        self.next_release = str(uuid4())

    async def when_user_up_env_again_with_force_restart(self):
        self.response = await UberCompose().up(
            compose_files='docker-compose.yaml',
            config_template=Environment(
                singleton(Service('db')),
                Service('app'),
            ),
            release_id=self.next_release,
            force_restart=True,
        )

    async def then_it_should_return_successful_code(self):
        assert self.response.env_id == schema.str

    async def then_singleton_should_be_restarted_because_force_restart_was_requested(self):
        self.containers = retrieve_all_docker_containers()
        assert self.containers == schema.list([
            ...,
            ContainerSchema % {
                'Labels': {
                    'com.docker.compose.service': 'db',
                    Label.RELEASE_ID: self.next_release,
                },
            },
            ...,
        ])
        assert not any(container['Id'] == self.db_container_id_before for container in self.containers)

    @retry(attempts=3, delay=1)
    async def then_singleton_migration_should_rerun_on_the_fresh_container(self):
        self.migration_log_after = get_file_from_container('db', self.migration_result_file)
        assert self.migration_log_after == schema.bytes % b'db migration done\n'
