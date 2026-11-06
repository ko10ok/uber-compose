from contexts.compose_file import compose_file
from contexts.isolated_project import isolated_constants
from contexts.isolated_project import isolated_project
from contexts.no_docker_containers import no_docker_containers
from contexts.no_docker_containers import retrieve_all_docker_containers
from d42 import schema
from schemas.docker import ContainerSchema
import vedro
from vedro import catched
from yaml.parser import ParserError

from uber_compose import Environment
from uber_compose import Service
from uber_compose.uber_compose import UberCompose


class Scenario(vedro.Scenario):
    async def given_no_docker_containers(self):
        no_docker_containers()

    async def given_isolated_project(self):
        self.project = isolated_project()
        self.instance_files_root = self.project.tmp_envs_path
        self.constants = isolated_constants(self.project)

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
            await UberCompose(cfg_constants=self.constants, ).up(
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
        self.response = await UberCompose(cfg_constants=self.constants, ).up(
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
                    'com.docker.compose.project.config_files': (
                        f'{self.instance_files_root}/default_env_id/'
                        f'docker-compose.dev.yaml'
                    ),
                },
            },
        ])
