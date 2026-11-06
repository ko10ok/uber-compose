from contexts.compose_file import compose_file
from contexts.isolated_project import isolated_constants
from contexts.isolated_project import isolated_project
from contexts.no_docker_containers import no_docker_containers
from contexts.no_docker_containers import retrieve_all_docker_containers
from contexts.services_started import services_started
import vedro

from uber_compose import Environment
from uber_compose import Service


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

    async def given_env_already_up_with_parallelism_limit(self):
        self.first_response = await services_started(
            constants=self.constants,
            compose_files=self.compose_files,
            config_template=self.environment,
            parallelism_limit=2,
        )
        self.first_containers = retrieve_all_docker_containers()

    async def when_user_up_same_env_again_with_parallelism_limit(self):
        self.second_response = await services_started(
            constants=self.constants,
            compose_files=self.compose_files,
            config_template=self.environment,
            parallelism_limit=2,
        )

    async def then_it_should_return_the_same_env_id(self):
        assert self.second_response.env_id == self.first_response.env_id

    async def and_it_should_not_create_new_containers(self):
        self.second_containers = retrieve_all_docker_containers()
        first_ids = {container['Id'] for container in self.first_containers}
        second_ids = {container['Id'] for container in self.second_containers}
        assert second_ids == first_ids
