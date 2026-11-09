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
    subject = 'use all parameterization placeholders with unsafe namespace'

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
            'UC_WORKER_ID': '3',
            'UC_WORKERS_TOTAL': '4',
        })

    async def given_env_with_all_placeholders(self):
        self.environment = Environment(
            Service('s1', env=Env({
                'ENV_ID': '[[env_id]]',
                'WORKER_ID': '[[worker_id]]',
                'NAMESPACE': '[[namespace]]',
                'WORKER_ALPHA_NUMERIC': '[[worker_id_alpha_numeric]]',
                'NAMESPACE_ALPHA_NUMERIC': '[[namespace_alpha_numeric]]',
                'WORKER_ALPHA_NUMERIC_6': '[[worker_id_alpha_numeric_6]]',
                'NAMESPACE_ALPHA_NUMERIC_6': '[[namespace_alpha_numeric_6]]',
                'RUN': '[[test_run_id]]',
                'SERVICE': '[[s1]]',
            })),
            description='env-a',
        )

    async def when_user_up_env_with_unsafe_env_id(self):
        self.env_id = '2-bad.id'
        self.run_id = 'run-alpha'
        self.response = await UberCompose(
            cfg_constants=self.constants,
            run_id=self.run_id,
        ).up(
            compose_files=self.compose_files,
            config_template=self.environment,
            parallelism_limit=4,
            env_id=self.env_id,
        )

    async def then_all_placeholders_should_be_substituted(self):
        service_env = dict(self.response.env['s1'].env)
        assert service_env['ENV_ID'] == '2-bad.id'
        assert service_env['WORKER_ID'] == '3'
        assert service_env['NAMESPACE'] == '2-bad.id'
        assert service_env['WORKER_ALPHA_NUMERIC'] == 'w3'
        assert service_env['NAMESPACE_ALPHA_NUMERIC'] == 'k2badid'
        assert service_env['WORKER_ALPHA_NUMERIC_6'] == 'tfb7zb'
        assert service_env['NAMESPACE_ALPHA_NUMERIC_6'] == 'zulhci'
        assert service_env['RUN'] == 'run-alpha'
        assert service_env['SERVICE'] == 's1-2-bad.id'
