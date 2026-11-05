from contexts.compose_file import compose_file
from contexts.isolated_project import isolated_constants
from contexts.isolated_project import isolated_project
from contexts.no_docker_containers import no_docker_containers
from contexts.no_docker_containers import retrieve_all_docker_containers
from contexts.services_started import services_started
from d42 import schema
from schemas.docker import ContainerSchema
import vedro

from uber_compose import DEFAULT_ENV_ID
from uber_compose import Environment
from uber_compose import Service
from uber_compose.helpers.labels import Label


class Scenario(vedro.Scenario):
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
  s1:
    image: busybox:stable
    command: 'sh -c "trap : TERM INT; sleep 604800; wait"'
"""
        )

    async def given_env_template(self):
        self.environment = Environment(Service('s1'), description='env-a')

    async def given_env_up_with_explicit_env_id_and_parallelism_limit_1(self):
        self.first_response = await services_started(
            constants=self.constants,
            compose_files=self.compose_files,
            config_template=self.environment,
            parallelism_limit=1,
            env_id='w0-alpha',
        )
        self.first_containers = retrieve_all_docker_containers()

    async def when_user_up_same_env_without_env_id_and_parallelism_limit_1(self):
        self.second_response = await services_started(
            constants=self.constants,
            compose_files=self.compose_files,
            config_template=self.environment,
            parallelism_limit=1,
        )

    async def then_it_should_ignore_explicit_env_id_and_use_default(self):
        assert self.first_response.env_id == DEFAULT_ENV_ID
        assert self.second_response.env_id == DEFAULT_ENV_ID

    async def and_it_should_have_default_unsuffixed_service_name(self):
        self.containers = retrieve_all_docker_containers()
        assert self.containers == schema.list([
            ...,
            ContainerSchema % {
                'Labels': {
                    'com.docker.compose.service': 's1',
                    Label.ENV_ID: DEFAULT_ENV_ID,
                    Label.ENV_DESCRIPTION: str(self.environment),
                },
            },
            ...,
        ])

    async def and_it_should_reuse_the_same_container(self):
        first_ids = {container['Id'] for container in self.first_containers}
        second_ids = {container['Id'] for container in self.containers}
        assert second_ids == first_ids
