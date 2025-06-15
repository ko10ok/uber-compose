import vedro
from d42 import schema
from vedro import catched

from contexts.compose_file import compose_file
from contexts.no_docker_compose_files import no_docker_compose_files
from contexts.no_docker_containers import no_docker_containers
from contexts.no_docker_containers import retrieve_all_docker_containers
from schemas.docker import ContainerSchema
from uber_compose import Environment
from uber_compose import Service
from uber_compose.uber_compose import UberCompose
from uber_compose.errors.up import ServicesUpError
from uber_compose.helpers.health_policy import UpHealthPolicy


class Scenario(vedro.Scenario):
    async def no_docker_containers(self):
        no_docker_containers()

    async def no_docker_copose_files(self):
        no_docker_compose_files()

    async def given_compose_files(self):
        compose_file(
            'docker-compose.yaml',
            content="""
version: "3"

services:
  s1:
    image: busybox:stable
    command: 'sh -c "echo error service exception log && sleep 5000 && echo `date +%s` > /tmp/healthcheck; trap : 
    TERM INT; sleep 604800; wait"'
    healthcheck:
      test: ["CMD", "sh", "-c", "[ -f /tmp/healthcheck ] || exit 1"]
      interval: 5s
      timeout: 10s
      retries: 100

  s2:
    image: busybox:stable
    command: 'sh -c "trap : TERM INT; sleep 604800; wait"'
    depends_on:
        - s1
    
"""
        )
        compose_file(
            'docker-compose.dev.yaml',
            content="""
version: "3"

services:
  s2:
    image: busybox:stable
    command: 'sh -c "trap : TERM INT; sleep 604800; wait"'
"""
        )

    async def when_user_up_env(self):
        with catched(ServicesUpError) as self.exc_info:
            self.response = await UberCompose(
                health_policy=UpHealthPolicy(service_up_check_attempts=3, service_up_check_delay_s=1),
            ).up(
                compose_files='docker-compose.yaml:docker-compose.dev.yaml',
                config_template=Environment(
                    Service('s1'), Service('s2')
                )
            )

    async def then_it_should_out_services_logs(self):
        self.exception_str = str(self.exc_info.value)
        assert "Can't up services" in self.exception_str
        assert "s1" in self.exception_str
        assert "starting" in self.exception_str

    async def then_it_should_up_only_first_tier_services(self):
        self.containers = retrieve_all_docker_containers()
        assert self.containers == schema.list([
            ContainerSchema % {
                'Labels': {
                    'com.docker.compose.service': 's1',
                    'com.docker.compose.project.config_files':
                        '/tmp-envs/no_id/docker-compose.yaml,/tmp-envs/no_id/docker-compose.dev.yaml',
                },
            },
        ])
