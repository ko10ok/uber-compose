from contexts.compose_file import compose_file
from contexts.isolated_project import isolated_constants
from contexts.isolated_project import isolated_project
from contexts.no_docker_containers import no_docker_containers
import vedro

from uber_compose import Env
from uber_compose import Environment
from uber_compose import Service
from uber_compose.uber_compose import UberCompose


class Scenario(vedro.Scenario):
    subject = 'use env_id placeholder in service env parameters'

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

    async def given_env_with_env_id_placeholders(self):
        self.environment = Environment(
            Service('s1', env=Env({
                'DB_NAME': 'app_[[env_id]]',
                'SERVICE_NAME': '[[s1]]',
            })),
            description='env-a',
        )

    async def when_user_up_env_with_explicit_env_id(self):
        self.env_id = 'w3-test'
        self.response = await UberCompose(
            cfg_constants=self.constants,
        ).up(
            compose_files=self.compose_files,
            config_template=self.environment,
            parallelism_limit=2,
            env_id=self.env_id,
        )

    async def then_env_id_placeholder_should_be_substituted(self):
        service_env = dict(self.response.env['s1'].env)
        assert service_env['DB_NAME'] == 'app_w3-test'

    async def and_service_name_placeholder_should_be_substituted(self):
        service_env = dict(self.response.env['s1'].env)
        assert service_env['SERVICE_NAME'] == 's1-w3-test'
