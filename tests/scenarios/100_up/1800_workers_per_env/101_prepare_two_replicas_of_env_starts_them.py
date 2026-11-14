from contexts.compose_file import compose_file
from contexts.isolated_project import isolated_constants
from contexts.isolated_project import isolated_project
from contexts.no_docker_containers import no_docker_containers
from contexts.no_docker_containers import retrieve_all_docker_containers
from d42 import schema
from schemas.docker import ContainerSchema
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

    async def when_user_prepares_two_replicas_of_env(self):
        self.ready_envs = await UberCompose(
            cfg_constants=self.constants,
        ).prepare_parallel_environments(
            config_templates=[self.environment],
            compose_files=self.compose_files,
            workers_per_env={'env-a': 2},
        )

    async def then_it_should_start_two_replicas_with_stable_env_ids(self):
        assert len(self.ready_envs) == 2
        assert {ready_env.env_id for ready_env in self.ready_envs} == {
            get_stable_env_id(self.environment, 0),
            get_stable_env_id(self.environment, 1),
        }

    async def and_it_should_have_two_isolated_containers(self):
        self.containers = retrieve_all_docker_containers()
        assert len(self.containers) == 2
        for index in range(2):
            env_id = get_stable_env_id(self.environment, index)
            assert self.containers == schema.list([
                ...,
                ContainerSchema % {
                    'Labels': {
                        'com.docker.compose.service': f's1-{env_id}',
                        Label.ENV_ID: env_id,
                    },
                },
                ...,
            ])
