from contexts.compose_file import compose_file
from contexts.isolated_project import isolated_constants
from contexts.isolated_project import isolated_project
from contexts.no_docker_containers import no_docker_containers
from contexts.no_docker_containers import retrieve_all_docker_containers
import vedro

from uber_compose import Environment
from uber_compose import Service
from uber_compose.core.utils.compose_instance_cfg import get_stable_env_id
from uber_compose.helpers.labels import Label
from uber_compose.uber_compose import UberCompose


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

    async def given_one_replica_of_env_is_prepared(self):
        self.first_ready_envs = await UberCompose(
            cfg_constants=self.constants,
        ).prepare_parallel_environments(
            config_templates=[self.environment],
            compose_files=self.compose_files,
            workers_per_env={'env-a': 1},
        )
        self.first_container_id = retrieve_all_docker_containers()[0]['Id']

    async def when_user_prepares_two_replicas_of_same_env(self):
        self.second_ready_envs = await UberCompose(
            cfg_constants=self.constants,
        ).prepare_parallel_environments(
            config_templates=[self.environment],
            compose_files=self.compose_files,
            workers_per_env={'env-a': 2},
        )

    async def then_it_should_keep_existing_replica_and_add_missing_one(self):
        first_env_id = get_stable_env_id(self.environment, 0)
        second_env_id = get_stable_env_id(self.environment, 1)
        assert len(self.second_ready_envs) == 2
        assert {ready_env.env_id for ready_env in self.second_ready_envs} == {
            first_env_id,
            second_env_id,
        }

    async def and_it_should_not_recreate_the_existing_replica(self):
        containers = retrieve_all_docker_containers()
        assert len(containers) == 2
        first_env_id = get_stable_env_id(self.environment, 0)
        existing = [
            container for container in containers
            if container.get('Labels', {}).get(Label.ENV_ID) == first_env_id
        ]
        assert len(existing) == 1
        assert existing[0]['Id'] == self.first_container_id
