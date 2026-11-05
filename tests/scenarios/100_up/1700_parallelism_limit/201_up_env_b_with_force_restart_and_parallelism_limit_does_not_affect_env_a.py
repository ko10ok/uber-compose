from contexts.compose_file import compose_file
from contexts.no_docker_compose_files import no_docker_compose_files
from contexts.no_docker_containers import no_docker_containers
from contexts.no_docker_containers import retrieve_all_docker_containers
from contexts.services_started import services_started
import vedro

from uber_compose import Environment
from uber_compose import Service


class Scenario(vedro.Scenario):
    async def given_no_docker_containers(self):
        no_docker_containers()

    async def given_no_docker_compose_files(self):
        no_docker_compose_files()

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

    async def given_two_env_templates(self):
        self.environment_a = Environment(Service('s1'), description='env-a')
        self.environment_b = Environment(Service('s1'), description='env-b')

    async def given_env_a_already_up_with_parallelism_limit(self):
        self.response_a = await services_started(
            compose_files=self.compose_files,
            config_template=self.environment_a,
            parallelism_limit=2,
        )
        self.containers_a_before = retrieve_all_docker_containers()

    async def given_env_b_already_up_with_parallelism_limit(self):
        self.response_b = await services_started(
            compose_files=self.compose_files,
            config_template=self.environment_b,
            parallelism_limit=2,
        )

    async def when_user_up_env_b_again_with_force_restart_and_parallelism_limit(self):
        self.response_b_restarted = await services_started(
            compose_files=self.compose_files,
            config_template=self.environment_b,
            parallelism_limit=2,
            force_restart=True,
        )

    async def then_env_a_containers_should_be_untouched(self):
        self.containers = retrieve_all_docker_containers()
        env_a_ids_before = {
            container['Id']
            for container in self.containers_a_before
            if container['Labels'].get('com.maxwelld.env_id') == self.response_a.env_id
        }
        env_a_ids_after = {
            container['Id']
            for container in self.containers
            if container['Labels'].get('com.maxwelld.env_id') == self.response_a.env_id
        }
        assert env_a_ids_after == env_a_ids_before
        assert len(env_a_ids_after) != 0

    async def and_env_b_should_have_been_restarted(self):
        assert self.response_b_restarted.env_id != self.response_b.env_id
        assert self.response_b_restarted.env_id != self.response_a.env_id
