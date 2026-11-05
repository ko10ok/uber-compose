from contexts.compose_file import compose_file
from contexts.isolated_project import isolated_constants
from contexts.isolated_project import isolated_project
from contexts.no_docker_containers import no_docker_containers
from helpers.env_vars import patch_env
import vedro

from uber_compose import Env
from uber_compose import Environment
from uber_compose import Service
from uber_compose.uber_compose import UberCompose


class Scenario(vedro.Scenario):
    subject = 'use worker id namespace and test run id placeholders in service env parameters'

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

    async def given_worker_environment(self):
        patch_env({
            'UC_WORKER_ID': '2',
            'UC_WORKERS_TOTAL': '4',
        })

    async def given_env_with_worker_placeholders(self):
        self.environment = Environment(
            Service('s1', env=Env({
                'WORKER': 'w[[worker_id]]',
                'NAMESPACE': 'n_[[namespace]]',
                'RUN': 'r_[[test_run_id]]',
            })),
            description='env-a',
        )

    async def when_user_up_env_with_explicit_env_id_and_run_id(self):
        self.env_id = 'w2-abc'
        self.run_id = 'run-xyz'
        self.response = await UberCompose(
            cfg_constants=self.constants,
            run_id=self.run_id,
        ).up(
            compose_files=self.compose_files,
            config_template=self.environment,
            parallelism_limit=4,
            env_id=self.env_id,
        )

    async def then_worker_namespace_and_run_placeholders_should_be_substituted(self):
        service_env = dict(self.response.env['s1'].env)
        assert service_env['WORKER'] == 'w2'
        assert service_env['NAMESPACE'] == 'n_w2-abc'
        assert service_env['RUN'] == 'r_run-xyz'
