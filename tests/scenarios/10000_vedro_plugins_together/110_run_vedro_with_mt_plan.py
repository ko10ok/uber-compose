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
    subject = 'run vedro with parallel plan and do not start anything'

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
        for index in range(4):
            scenarios[f'test_env_a_{index}.py'] = SCENARIO_TEMPLATE.format(
                subject=f'env-a scenario {index}',
                env_description='env-a',
            )
        for index in range(2):
            scenarios[f'test_env_b_{index}.py'] = SCENARIO_TEMPLATE.format(
                subject=f'env-b scenario {index}',
                env_description='env-b',
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
                    workers_per_env={{"env-a": 2, "env-b": 1}},
                ),
            }}

        class UberComposeParallel(VedroUberComposeParallel):
            enabled = True
""",
            scenarios=scenarios,
        )

    async def when_vedro_is_run_with_parallel_plan(self):
        self.run_result = await CliRunner().run_vedro(
            self.project_dir,
            args=['run', 'scenarios/', '--uc-mt', '--uc-mt-plan'],
        )

    async def then_it_should_exit_with_code_zero(self):
        assert self.run_result.returncode == 0, self.run_result.stdout + self.run_result.stderr

    async def and_it_should_show_envs_workers_and_tests(self):
        stdout = self.run_result.stdout
        assert 'uber-compose plan' in stdout
        assert 'dry run: nothing will be started' in stdout
        assert 'lifecycle: env-a[2] || env-b[1]' in stdout
        assert 'infra: root_orchestrator -> workers[3]' in stdout
        assert 'w0-env-a[0]  tests[2]: test_env_a_0.py, test_env_a_2.py' in stdout
        assert 'w1-env-a[1]  tests[2]: test_env_a_1.py, test_env_a_3.py' in stdout
        assert 'w2-env-b[0]  tests[2]: test_env_b_0.py, test_env_b_1.py' in stdout

    async def when_level_one_plan_is_run(self):
        self.level_one_result = await CliRunner().run_vedro(
            self.project_dir,
            args=['run', 'scenarios/', '--uc-mt', '--uc-mt-plan=1'],
        )

    async def then_it_should_show_namespaces_and_settings(self):
        assert self.level_one_result.returncode == 0
        stdout = self.level_one_result.stdout
        assert 'workers_per_env: env-a[2], env-b[1]' in stdout
        assert 'w0-env-a[0]  namespace: w0-' in stdout
        assert 'w1-env-a[1]  namespace: w1-' in stdout

    async def and_it_should_not_start_containers(self):
        assert retrieve_all_docker_containers() == []
