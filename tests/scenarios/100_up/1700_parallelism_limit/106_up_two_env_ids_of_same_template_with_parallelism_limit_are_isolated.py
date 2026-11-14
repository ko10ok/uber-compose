from contexts.compose_file import compose_file
from contexts.isolated_project import isolated_constants
from contexts.isolated_project import isolated_project
from contexts.no_docker_containers import no_docker_containers
from contexts.no_docker_containers import retrieve_all_docker_containers
from contexts.services_started import services_started
from d42 import schema
from schemas.docker import ContainerSchema
import vedro

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

    async def given_env_a_up_with_explicit_env_id(self):
        self.env_id_a = 'w0-first'
        self.response_a = await services_started(
            constants=self.constants,
            compose_files=self.compose_files,
            config_template=self.environment,
            parallelism_limit=2,
            env_id=self.env_id_a,
        )

    async def given_env_b_up_with_another_explicit_env_id(self):
        self.env_id_b = 'w1-second'
        self.response_b = await services_started(
            constants=self.constants,
            compose_files=self.compose_files,
            config_template=self.environment,
            parallelism_limit=2,
            env_id=self.env_id_b,
        )

    async def when_user_up_env_a_again_with_its_env_id(self):
        self.response_a_again = await services_started(
            constants=self.constants,
            compose_files=self.compose_files,
            config_template=self.environment,
            parallelism_limit=2,
            env_id=self.env_id_a,
        )

    async def then_it_should_keep_both_envs_with_their_env_ids(self):
        assert self.response_a.env_id == self.env_id_a
        assert self.response_b.env_id == self.env_id_b
        assert self.response_a_again.env_id == self.env_id_a

    async def and_it_should_reuse_only_the_requested_env(self):
        self.containers = retrieve_all_docker_containers()
        assert len(self.containers) == 2
        assert self.containers == schema.list([
            ...,
            ContainerSchema % {
                'Labels': {
                    'com.docker.compose.service': f's1-{self.env_id_a}',
                    Label.ENV_ID: self.env_id_a,
                },
            },
            ...,
        ])
        assert self.containers == schema.list([
            ...,
            ContainerSchema % {
                'Labels': {
                    'com.docker.compose.service': f's1-{self.env_id_b}',
                    Label.ENV_ID: self.env_id_b,
                },
            },
            ...,
        ])
