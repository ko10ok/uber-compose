from contexts.compose_file import compose_file
from contexts.isolated_project import isolated_constants
from contexts.isolated_project import isolated_project
from contexts.no_docker_containers import no_docker_containers
from contexts.no_docker_containers import retrieve_all_docker_containers
from d42 import schema
from helpers.docker_container import get_containers_by_env_id
from helpers.docker_container import get_env_snapshot
from schemas.docker import ContainerSchema
import vedro
from vedro import catched

from uber_compose import Environment
from uber_compose import Service
from uber_compose.errors.up import ServicesUpError
from uber_compose.helpers.health_policy import UpHealthPolicy
from uber_compose.helpers.labels import Label
from uber_compose.uber_compose import UberCompose


class Scenario(vedro.Scenario):
    subject = 'parallel up healthy env b while env a exited unexpectedly'

    async def given_no_docker_containers(self):
        no_docker_containers()

    async def given_isolated_project(self):
        self.project = isolated_project()
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
    command: 'sh -c "exit 10"'

  good:
    image: busybox:stable
    command: 'sh -c "trap : TERM INT; sleep 604800; wait"'
"""
        )

    async def given_env_a_exited_unexpectedly(self):
        self.environment_a = Environment(Service('bad'), description='env-a')
        self.environment_b = Environment(Service('good'), description='env-b')
        self.env_id_a = 'w0-a'
        self.env_id_b = 'w0-b'
        with catched(ServicesUpError):
            await UberCompose(
                cfg_constants=self.constants,
                health_policy=UpHealthPolicy(
                    service_up_check_attempts=3,
                    service_up_check_delay_s=1,
                    pre_check_delay_s=1,
                ),
            ).up(
                compose_files=self.compose_files,
                config_template=self.environment_a,
                parallelism_limit=2,
                env_id=self.env_id_a,
            )
        self.snapshot_a = get_env_snapshot(self.env_id_a)

    async def when_user_up_healthy_env_b(self):
        self.response_b = await UberCompose(
            cfg_constants=self.constants,
            health_policy=UpHealthPolicy(
                service_up_check_attempts=3,
                service_up_check_delay_s=1,
                pre_check_delay_s=0,
            ),
        ).up(
            compose_files=self.compose_files,
            config_template=self.environment_b,
            parallelism_limit=2,
            env_id=self.env_id_b,
        )

    async def then_collect_all_containers(self):
        self.containers = retrieve_all_docker_containers()

    async def then_env_b_should_be_running(self):
        containers_b = get_containers_by_env_id(self.env_id_b, self.containers)
        assert len(containers_b) == 1
        assert containers_b[0]['State'] == 'running'

    async def then_env_a_should_be_untouched(self):
        for container_id, container_state in self.snapshot_a.items():
            assert self.containers == schema.list([
                ...,
                ContainerSchema % {
                    'Id': container_id,
                    'State': container_state['State'],
                    'Labels': {
                        'com.docker.compose.service': container_state['Service'],
                        Label.ENV_ID: self.env_id_a,
                    },
                },
                ...,
            ])
