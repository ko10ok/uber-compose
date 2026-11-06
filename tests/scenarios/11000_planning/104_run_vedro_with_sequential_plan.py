from contexts.compose_file import compose_file
from contexts.isolated_project import isolated_project
from contexts.no_docker_containers import no_docker_containers
from contexts.no_docker_containers import retrieve_all_docker_containers
from contexts.vedro_subprocess_project import vedro_subprocess_project
from interfaces.vedro_cli import CliRunner
import vedro

SCENARIO_TEMPLATE = """
import vedro

from uber_compose import Environment
from uber_compose import Service


class Scenario(vedro.Scenario):
    subject = '{subject}'
    env = Environment(Service('s1'), description='{env_description}')

    def when_nothing_special_happens(self):
        self.result = 'ok'

    def then_it_should_pass(self):
        assert self.result == 'ok'
"""


class Scenario(vedro.Scenario):
    subject = 'run vedro with sequential plan and do not start anything'

    async def given_no_docker_containers(self):
        no_docker_containers()

    async def given_isolated_project(self):
        self.project = isolated_project()
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

    async def given_vedro_project_with_two_envs(self):
        scenarios = {}
        for env_description in ('env-a', 'env-b'):
            for index in range(2):
                scenarios[f'test_{env_description}_{index}.py'] = SCENARIO_TEMPLATE.format(
                    subject=f'{env_description} scenario {index}',
                    env_description=env_description,
                )

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
                    max_concurrent_envs=1,
                ),
            }}

        class UberComposeParallel(VedroUberComposeParallel):
            enabled = True
""",
            scenarios=scenarios,
        )

    async def when_vedro_is_run_with_sequential_plan(self):
        self.run_result = await CliRunner().run_vedro(
            self.project_dir,
            args=['run', 'scenarios/', '--uc-mt-plan'],
        )

    async def then_it_should_exit_with_code_zero(self):
        assert self.run_result.returncode == 0, self.run_result.stdout + self.run_result.stderr

    async def and_it_should_show_root_worker_and_tests_by_env(self):
        stdout = self.run_result.stdout
        assert 'lifecycle: env-a -> env-b' in stdout
        assert 'infra: root_worker' in stdout
        assert "env-a\n  services: s1\n  tests[2]: test_env-a_0.py, test_env-a_1.py" in stdout
        assert "env-b\n  services: s1\n  tests[2]: test_env-b_0.py, test_env-b_1.py" in stdout

    async def and_it_should_not_start_containers(self):
        assert retrieve_all_docker_containers() == []
