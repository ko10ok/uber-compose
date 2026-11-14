from time import perf_counter

from contexts.compose_file import compose_file
from contexts.isolated_project import isolated_constants
from contexts.isolated_project import isolated_project
from contexts.no_docker_containers import no_docker_containers
from contexts.no_docker_containers import retrieve_all_docker_containers
from d42 import schema
from schemas.docker import ContainerSchema
import vedro

from uber_compose import Environment
from uber_compose import Service
from uber_compose.helpers.health_policy import UpHealthPolicy
from uber_compose.uber_compose import UberCompose


class Scenario(vedro.Scenario):
    subject = 'up env with unhealthy service with restart policy recovers'

    async def given_no_docker_containers(self):
        no_docker_containers()

    async def given_isolated_project(self):
        self.project = isolated_project()
        self.constants = isolated_constants(self.project)

    async def given_compose_file_with_unhealthy_service_that_recovers(self):
        self.compose_filename = 'docker-compose.basic.yaml'
        compose_file(
            self.compose_filename,
            content="""
version: "3"

services:
  s1:
    image: busybox:stable
    command:
      - sh
      - -c
      - |
        sleep 2
        touch /tmp/ready
        trap : TERM INT
        sleep 604800
        wait
    restart: on-failure
    healthcheck:
      test: ["CMD", "sh", "-c", "[ -f /tmp/ready ]"]
      interval: 200ms
      timeout: 1s
      retries: 1
"""
        )

    async def when_user_up_env_with_temporarily_unhealthy_service(self):
        self.started_at = perf_counter()
        self.response = await UberCompose(
            cfg_constants=self.constants,
            health_policy=UpHealthPolicy(
                service_up_check_attempts=50,
                service_up_check_delay_s=0.2,
                pre_check_delay_s=0,
            ),
        ).up(
            config_template=Environment(
                'DEFAULT',
                Service('s1')
            ),
            compose_files=self.compose_filename,
        )
        self.elapsed = perf_counter() - self.started_at

    async def then_up_function_should_finish_successfully(self):
        assert self.response.env_id == schema.str

    async def then_it_should_wait_for_service_to_become_healthy(self):
        assert self.elapsed < 15

    async def then_service_should_be_running(self):
        self.containers = retrieve_all_docker_containers()
        assert self.containers == schema.list([
            ContainerSchema % {
                'State': 'running',
                'Labels': {
                    'com.docker.compose.service': 's1',
                },
            },
        ])
