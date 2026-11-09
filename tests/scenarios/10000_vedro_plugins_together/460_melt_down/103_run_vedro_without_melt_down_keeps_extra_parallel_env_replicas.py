from contexts.compose_file import compose_file
from contexts.isolated_project import isolated_constants
from contexts.isolated_project import isolated_project
from contexts.no_docker_containers import no_docker_containers
from contexts.no_docker_containers import retrieve_all_docker_containers
from contexts.vedro_subprocess_project import vedro_subprocess_project
from d42 import schema
from interfaces.vedro_cli import CliRunner
from schemas.docker import ContainerSchema
import vedro

from uber_compose import Environment
from uber_compose import Service
from uber_compose.core.utils.compose_instance_cfg import get_stable_env_id
from uber_compose.helpers.labels import Label
from uber_compose.uber_compose import UberCompose

SCENARIO_TEMPLATE = """
import vedro

from uber_compose import Environment
from uber_compose import Service


class Scenario(vedro.Scenario):
    subject = 'passing __ENV__ scenario'
    env = Environment(Service('s1'), description='__ENV__')

    def when_nothing_special_happens(self):
        self.result = 'ok'

    def then_it_should_pass(self):
        assert self.result == 'ok'
"""


class Scenario(vedro.Scenario):
    subject = 'run vedro without melt down keeping extra parallel env replicas'

    async def given_no_docker_containers(self):
        no_docker_containers()

    async def given_isolated_project(self):
        self.project = isolated_project()
        self.constants = isolated_constants(self.project)
        self.compose_filename = 'docker-compose.yaml'
        compose_file(
            self.compose_filename,
            content="""
version: "3"

services:
  s1:
    image: busybox:stable
    command: 'sh -c "trap : TERM INT; sleep 604800; wait"'
"""
        )

    async def given_extra_replica_of_env_a_is_running(self):
        self.env_a = Environment(Service('s1'), description='env-a')
        self.extra_env_a_id = get_stable_env_id(self.env_a, 1)
        await UberCompose(
            cfg_constants=self.constants,
        ).prepare_parallel_environments(
            config_templates=[self.env_a],
            compose_files=self.compose_filename,
            workers_per_env={'env-a': 2},
        )

    async def given_vedro_project_with_two_envs(self):
        self.project_dir = vedro_subprocess_project(
            vedro_cfg=f"""
import vedro

from uber_compose import ComposeConfig
from uber_compose import DEFAULT_COMPOSE
from uber_compose import VedroUberCompose
from uber_compose import VedroUberComposeParallel


class Config(vedro.Config):
    class Plugins(vedro.Config.Plugins):
        class UberCompose(VedroUberCompose):
            enabled = True
            compose_cfgs = {{
                DEFAULT_COMPOSE: ComposeConfig(
                    compose_files="{self.compose_filename}",
                    workers_per_env={{"env-a": 1, "env-b": 1}},
                ),
            }}

        class UberComposeParallel(VedroUberComposeParallel):
            enabled = True
""",
            scenarios={
                'test_env_a.py': SCENARIO_TEMPLATE.replace('__ENV__', 'env-a'),
                'test_env_b.py': SCENARIO_TEMPLATE.replace('__ENV__', 'env-b'),
            },
        )

    async def when_vedro_is_run_without_melt_down(self):
        self.run_result = await CliRunner().run_vedro(
            self.project_dir,
            args=['run', 'scenarios/', '--uc-mt'],
        )

    async def then_it_should_exit_with_code_zero(self):
        assert self.run_result.returncode == 0, self.run_result.stdout + self.run_result.stderr

    async def and_extra_env_replica_should_stay_running(self):
        env_a_0_id = get_stable_env_id(self.env_a, 0)
        env_b_id = get_stable_env_id(
            Environment(Service('s1'), description='env-b'),
            0,
        )
        self.containers = retrieve_all_docker_containers()
        assert self.containers == schema.list.len(3)
        assert self.containers == schema.list([
            ...,
            ContainerSchema % {
                'Labels': {
                    'com.docker.compose.service': f's1-{env_a_0_id}',
                    Label.ENV_ID: env_a_0_id,
                },
            },
            ...,
        ])
        assert self.containers == schema.list([
            ...,
            ContainerSchema % {
                'Labels': {
                    'com.docker.compose.service': f's1-{self.extra_env_a_id}',
                    Label.ENV_ID: self.extra_env_a_id,
                },
            },
            ...,
        ])
        assert self.containers == schema.list([
            ...,
            ContainerSchema % {
                'Labels': {
                    'com.docker.compose.service': f's1-{env_b_id}',
                    Label.ENV_ID: env_b_id,
                },
            },
            ...,
        ])
