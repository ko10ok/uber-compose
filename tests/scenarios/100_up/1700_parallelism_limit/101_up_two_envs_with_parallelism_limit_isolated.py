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

    async def given_two_env_templates(self):
        self.environment_a = Environment(Service('s1'), description='env-a')
        self.environment_b = Environment(Service('s1'), description='env-b')

    async def given_env_a_already_up_with_parallelism_limit(self):
        self.response_a = await services_started(
            constants=self.constants,
            compose_files=self.compose_files,
            config_template=self.environment_a,
            parallelism_limit=2,
        )

    async def when_user_up_env_b_with_parallelism_limit(self):
        self.response_b = await services_started(
            constants=self.constants,
            compose_files=self.compose_files,
            config_template=self.environment_b,
            parallelism_limit=2,
        )

    async def then_it_should_return_different_env_ids(self):
        assert self.response_a.env_id == schema.str
        assert self.response_b.env_id == schema.str
        assert self.response_a.env_id != self.response_b.env_id

    async def and_it_should_have_both_envs_containers_running(self):
        self.containers = retrieve_all_docker_containers()
        assert self.containers == schema.list([
            ...,
            ContainerSchema % {
                'Labels': {
                    'com.docker.compose.service': f's1-{self.response_a.env_id}',
                    Label.ENV_ID: self.response_a.env_id,
                    Label.ENV_DESCRIPTION: str(self.environment_a),
                },
            },
            ...,
        ])
        assert self.containers == schema.list([
            ...,
            ContainerSchema % {
                'Labels': {
                    'com.docker.compose.service': f's1-{self.response_b.env_id}',
                    Label.ENV_ID: self.response_b.env_id,
                    Label.ENV_DESCRIPTION: str(self.environment_b),
                },
            },
            ...,
        ])

    async def and_container_names_should_not_clash(self):
        assert len(self.containers) == 2
        names = {container['Names'][0] for container in self.containers}
        assert len(names) == 2
