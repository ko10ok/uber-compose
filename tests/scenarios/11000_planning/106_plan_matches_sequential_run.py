import json
from pathlib import Path
import re

from contexts.compose_file import compose_file
from contexts.isolated_project import isolated_project
from contexts.no_docker_containers import no_docker_containers
from contexts.no_docker_containers import retrieve_all_docker_containers
from contexts.vedro_subprocess_project import vedro_subprocess_project
from helpers.env_vars import patch_env
from interfaces.vedro_cli import CliRunner
import vedro
import vedro.plugins.temp_keeper as temp_keeper

SCENARIO_TEMPLATE = """
import json
import os

import vedro

from uber_compose import Environment
from uber_compose import Service


class Scenario(vedro.Scenario):
    subject = '{subject}'
    env = Environment(Service('s1'), description='{env_description}')

    def when_observation_is_recorded(self):
        observations_dir = os.environ['UC_TEST_OBSERVATIONS_DIR']
        with open(os.path.join(observations_dir, '{name}.json'), 'w') as file:
            json.dump({{
                'file': '{file_name}',
                'env_description': '{env_description}',
            }}, file)
"""

ENV_TESTS_LINE = re.compile(r'^\s+tests\[\d+\]: (?P<tests>.+)$')


class Scenario(vedro.Scenario):
    subject = 'plan matches actual sequential run'

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

    async def given_observations_directory(self):
        self.observations_dir = temp_keeper.create_tmp_dir(prefix='uc-plan-sequential-')
        patch_env({'UC_TEST_OBSERVATIONS_DIR': str(self.observations_dir)})

    async def given_vedro_project_with_two_envs(self):
        scenarios = {}
        for env_description in ('env-a', 'env-b'):
            for index in range(3):
                name = f"{env_description.replace('-', '_')}_{index}"
                file_name = f'test_{name}.py'
                scenarios[file_name] = SCENARIO_TEMPLATE.format(
                    subject=f'{env_description} scenario {index}',
                    env_description=env_description,
                    name=name,
                    file_name=file_name,
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

    async def when_plan_is_rendered(self):
        self.plan_result = await CliRunner().run_vedro(
            self.project_dir,
            args=['run', 'scenarios/', '--uc-mt-plan=1'],
        )

    async def then_plan_should_be_rendered_without_containers(self):
        assert self.plan_result.returncode == 0, self.plan_result.stdout + self.plan_result.stderr
        assert retrieve_all_docker_containers() == []
        self.planned_envs = self._parse_envs(self.plan_result.stdout)
        assert set(self.planned_envs) == {'env-a', 'env-b'}

    async def when_actual_sequential_run_is_finished(self):
        self.run_result = await CliRunner().run_vedro(
            self.project_dir,
            args=['run', 'scenarios/'],
        )

    async def then_actual_run_should_succeed(self):
        assert self.run_result.returncode == 0, self.run_result.stdout + self.run_result.stderr

    async def and_actual_tests_should_match_plan_by_env(self):
        observations = [
            json.loads(file.read_text())
            for file in self.observations_dir.glob('*.json')
        ]
        actual_envs = {}
        for observation in observations:
            actual_envs.setdefault(observation['env_description'], set()).add(
                Path(observation['file']).name
            )

        assert actual_envs == self.planned_envs

    def _parse_envs(self, stdout: str) -> dict[str, set[str]]:
        environments = {}
        current_env = None
        for line in stdout.splitlines():
            if line and not line.startswith(' '):
                if line.startswith('uber-compose') or line.startswith('dry run'):
                    continue
                if ': ' in line:
                    continue
                if line == 'settings:':
                    continue
                current_env = line
                environments[current_env] = set()
                continue

            match = ENV_TESTS_LINE.match(line)
            if match and current_env is not None:
                environments[current_env] = {
                    Path(test.strip()).name
                    for test in match.group('tests').split(',')
                }
        return environments
