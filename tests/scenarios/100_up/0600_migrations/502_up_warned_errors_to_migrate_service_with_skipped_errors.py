import vedro
from d42 import schema
from vedro import catched

from contexts.compose_file import compose_file
from contexts.no_docker_compose_files import no_docker_compose_files
from contexts.no_docker_containers import no_docker_containers
from uber_compose import Environment
from uber_compose import Service
from uber_compose.errors.up import ServicesUpError
from uber_compose.helpers.health_policy import UpHealthPolicy
from uber_compose.uber_compose import UberCompose


class Scenario(vedro.Scenario):
    async def no_docker_containers(self):
        no_docker_containers()

    async def no_docker_copose_files(self):
        no_docker_compose_files()

    async def given_compose_files(self):
        compose_file(
            'docker-compose.dev.yaml',
            content="""
version: "3"

services:
  s2:
    image: busybox:stable
    command: 'sh -c "trap : TERM INT; sleep 604800; wait"'
    x-migration:
        - after_start: sh -c 'sleep && echo 1 > /tmp/migration.log'
"""
        )

    async def when_user_up_env_without_params(self):
        with catched(ServicesUpError) as self.exc_info:
            self.response = await UberCompose(
                health_policy=UpHealthPolicy(
                    service_up_check_attempts=3,
                    service_up_check_delay_s=1,
                    skip_migrations_errors=[b'sleep: missing operand'],
                ),
            ).up(
                config_template=Environment(
                    'DEFAULT',
                    Service('s2')
                ),
                compose_files='docker-compose.dev.yaml',
            )

    async def then_it_should_out_services_logs(self):
        assert self.exc_info.value == schema.none
