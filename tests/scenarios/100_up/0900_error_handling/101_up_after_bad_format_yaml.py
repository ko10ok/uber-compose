import vedro
from d42 import fake
from d42 import schema

from vedro import catched
from yaml.parser import ParserError

from contexts.compose_file import compose_file
from contexts.no_docker_compose_files import no_docker_compose_files
from contexts.no_docker_containers import no_docker_containers
from contexts.no_docker_containers import retrieve_all_docker_containers
from schemas.docker import ContainerSchema
from schemas.env_name import EnvNameSchema
from uber_compose import Environment
from uber_compose import Service
from uber_compose.uber_compose import UberCompose
from uber_compose.errors.up import ServicesUpError


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
        - after_start: echo 1
    - after_start: echo 1
"""
        )

    async def given_no_params_for_env_to_up(self):
        with catched(ParserError) as self.started_error:
            await UberCompose().up(
                compose_files='docker-compose.dev.yaml',
                config_template=Environment(
                    Service('s2')
                )
            )

    async def given_next_compose_files(self):
        compose_file(
            'docker-compose.dev.yaml',
            content="""
    version: "3"

    services:
      s2:
        image: busybox:stable
        command: 'sh -c "trap : TERM INT; sleep 604800; wait"'
        x-migration:
          - after_start: echo 1
    """
        )

    async def when_user_up_env_without_params(self):
        self.response = await UberCompose().up(
            compose_files='docker-compose.dev.yaml',
            config_template=Environment(
                Service('s2')
            )
        )

    async def then_it_should_return_successful_code(self):
        assert self.response.env_id == schema.str

    async def then_it_should_up_entire_env(self):
        self.containers = retrieve_all_docker_containers()
        assert self.containers == schema.list([
            ContainerSchema % {
                'Labels': {
                    'com.docker.compose.service': 's2',
                    'com.docker.compose.project.config_files': '/tmp-envs/default_env_id/docker-compose.dev.yaml',
                },
            },
        ])
