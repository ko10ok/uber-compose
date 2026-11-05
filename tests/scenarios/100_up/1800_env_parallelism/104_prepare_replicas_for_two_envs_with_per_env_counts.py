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

    async def given_two_env_templates(self):
        self.environment_a = Environment(Service('s1'), description='env-a')
        self.environment_b = Environment(Service('s1'), description='env-b')

    async def when_user_prepares_replicas_with_per_env_counts(self):
        self.ready_envs = await UberCompose(
            cfg_constants=self.constants,
        ).prepare_parallel_environments(
            config_templates=[self.environment_a, self.environment_b],
            compose_files=self.compose_files,
            env_parallelism={'env-a': 2, 'env-b': 1},
        )

    async def then_it_should_start_replicas_for_each_env(self):
        expected_env_ids = {
            get_stable_env_id(self.environment_a, 0),
            get_stable_env_id(self.environment_a, 1),
            get_stable_env_id(self.environment_b, 0),
        }
        assert {ready_env.env_id for ready_env in self.ready_envs} == expected_env_ids

    async def and_it_should_have_one_container_per_replica(self):
        containers = retrieve_all_docker_containers()
        assert len(containers) == 3
        assert {container.get('Labels', {}).get(Label.ENV_ID) for container in containers} == {
            get_stable_env_id(self.environment_a, 0),
            get_stable_env_id(self.environment_a, 1),
            get_stable_env_id(self.environment_b, 0),
        }
