from contexts.compose_file import compose_file
from contexts.isolated_project import isolated_constants
from contexts.isolated_project import isolated_project
from contexts.no_docker_containers import no_docker_containers
from contexts.no_docker_containers import retrieve_all_docker_containers
from contexts.services_started import services_started
from d42 import schema
from schemas.docker import ContainerSchema
import vedro

from uber_compose import Env
from uber_compose import Environment
from uber_compose import Service
from uber_compose.helpers.exec_result import ExecResult
from uber_compose.helpers.labels import Label
from uber_compose.uber_compose import UberCompose


class Scenario(vedro.Scenario):
    subject = 'exec with explicit env_id in parallel namespaces reaches the requested container'

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

    async def given_two_namespaces_of_same_service_with_different_markers(self):
        self.environment_a = Environment(Service('s1', Env({'ENV_MARKER': 'a'})), description='env-a')
        self.environment_b = Environment(Service('s1', Env({'ENV_MARKER': 'b'})), description='env-b')

        self.response_a = await services_started(
            constants=self.constants,
            compose_files=self.compose_files,
            config_template=self.environment_a,
            parallelism_limit=2,
        )
        self.response_b = await services_started(
            constants=self.constants,
            compose_files=self.compose_files,
            config_template=self.environment_b,
            parallelism_limit=2,
        )
        self.containers = retrieve_all_docker_containers()

    async def when_user_exec_in_env_a_namespace(self):
        self.response_exec_a = await UberCompose(cfg_constants=self.constants, ).exec(
            container='s1',
            command='echo $ENV_MARKER',
            env_id=self.response_a.env_id,
        )

    async def when_user_exec_in_env_b_namespace(self):
        self.response_exec_b = await UberCompose(cfg_constants=self.constants, ).exec(
            container='s1',
            command='echo $ENV_MARKER',
            env_id=self.response_b.env_id,
        )

    async def then_env_a_and_env_b_should_be_different_namespaces(self):
        assert self.response_a.env_id == schema.str
        assert self.response_b.env_id == schema.str
        assert self.response_a.env_id != self.response_b.env_id

    async def then_both_namespaces_should_be_running(self):
        assert self.containers == schema.list([
            ...,
            ContainerSchema % {
                'Labels': {
                    'com.docker.compose.service': f's1-{self.response_a.env_id}',
                    Label.ENV_ID: self.response_a.env_id,
                    Label.TEMPLATE_SERVICE_NAME: 's1',
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
                    Label.TEMPLATE_SERVICE_NAME: 's1',
                },
            },
            ...,
        ])
        assert len(self.containers) == 2

    async def then_exec_in_env_a_should_reach_env_a_container(self):
        assert isinstance(self.response_exec_a, ExecResult)
        assert self.response_exec_a.stdout == schema.bytes(b'a\n')

    async def then_exec_in_env_b_should_reach_env_b_container(self):
        assert isinstance(self.response_exec_b, ExecResult)
        assert self.response_exec_b.stdout == schema.bytes(b'b\n')
