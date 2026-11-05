import asyncio

from contexts.compose_file import compose_file
from contexts.isolated_project import isolated_constants
from contexts.isolated_project import isolated_project
from contexts.no_docker_containers import no_docker_containers
from contexts.no_docker_containers import retrieve_all_docker_containers
from d42 import schema
from helpers.docker_container import get_container_by_service
from schemas.docker import ContainerSchema
import vedro
from vedro import catched

from uber_compose import Environment
from uber_compose import Service
from uber_compose.errors.up import ServicesUpError
from uber_compose.helpers.health_policy import UpHealthPolicy
from uber_compose.helpers.labels import Label
from uber_compose.uber_compose import UberCompose

UP_TIMEOUT_S = 60


class Scenario(vedro.Scenario):
    subject = 'up with healthy env b while neighbour env a is unhealthy'

    async def given_no_docker_containers(self):
        no_docker_containers()

    async def given_isolated_project(self):
        self.project = isolated_project()
        self.instance_files_root = self.project.tmp_envs_path
        self.constants = isolated_constants(self.project)

    async def given_compose_files(self):
        self.compose_files = 'docker-compose.yaml'
        compose_file(
            self.compose_files,
            content="""
version: "3"

services:
  bad:
    image: busybox:stable
    command: 'sh -c "trap : TERM INT; sleep 604800; wait"'
    healthcheck:
      test: ["CMD", "sh", "-c", "false"]
      interval: 1s
      timeout: 1s
      retries: 1

  good:
    image: busybox:stable
    command: 'sh -c "trap : TERM INT; sleep 604800; wait"'
"""
        )

    async def given_env_a_with_unhealthy_service_left_running(self):
        self.environment_a = Environment(Service('bad'), description='env-a')
        with catched(ServicesUpError):
            await asyncio.wait_for(
                UberCompose(
                    cfg_constants=self.constants,
                    health_policy=UpHealthPolicy(
                        service_up_check_attempts=1,
                        service_up_check_delay_s=0,
                        pre_check_delay_s=0,
                    ),
                ).up(
                    compose_files=self.compose_files,
                    config_template=self.environment_a,
                    parallelism_limit=2,
                ),
                timeout=UP_TIMEOUT_S,
            )
        self.containers_after_env_a = retrieve_all_docker_containers()
        assert self.containers_after_env_a == schema.list([
            ContainerSchema % {
                'State': 'running',
                'Labels': {
                    Label.TEMPLATE_SERVICE_NAME: 'bad',
                },
            },
        ])
        self.env_a_container = get_container_by_service('bad')
        self.env_a_container_id = self.env_a_container['Id']

    async def when_user_up_env_b_with_healthy_service(self):
        self.environment_b = Environment(Service('good'), description='env-b')
        self.response_b = await asyncio.wait_for(
            UberCompose(
                cfg_constants=self.constants,
                health_policy=UpHealthPolicy(
                    service_up_check_attempts=2,
                    service_up_check_delay_s=1,
                    pre_check_delay_s=0,
                ),
            ).up(
                compose_files=self.compose_files,
                config_template=self.environment_b,
                parallelism_limit=2,
            ),
            timeout=UP_TIMEOUT_S,
        )
        self.containers = retrieve_all_docker_containers()

    async def then_env_b_should_have_been_up_successfully(self):
        assert self.response_b.env_id == schema.str

    async def then_env_b_container_should_be_running(self):
        assert self.containers == schema.list([
            ...,
            ContainerSchema % {
                'State': 'running',
                'Labels': {
                    Label.TEMPLATE_SERVICE_NAME: 'good',
                },
            },
            ...,
        ])

    async def then_unhealthy_neighbour_should_still_be_running_and_untouched(self):
        assert self.containers == schema.list([
            ...,
            ContainerSchema % {
                'Id': self.env_a_container_id,
                'State': 'running',
                'Labels': {
                    Label.TEMPLATE_SERVICE_NAME: 'bad',
                },
            },
            ...,
        ])

    async def then_there_should_be_exactly_two_containers(self):
        assert len(self.containers) == 2
