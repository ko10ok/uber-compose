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
from uber_compose import TheUberCompose


class Scenario(vedro.Scenario):
    subject = '{subject}'
    env = Environment(Service('s1'), description='{env_description}')

    def when_observation_is_recorded(self):
        client = TheUberCompose
        observations_dir = os.environ['UC_TEST_OBSERVATIONS_DIR']
        with open(os.path.join(observations_dir, '{name}.json'), 'w') as file:
            json.dump({{
                'file': '{file_name}',
                'env_id': client.current_env_id(),
                'namespace': client.current_namespace(),
                'worker_id': client.current_worker_id(),
            }}, file)
"""

WORKER_LINE = re.compile(
    r'^\s+w(?P<worker_id>\d+)-(?P<env>[^\[]+)\[(?P<replica>\d+)\]'
    r'\s+namespace: (?P<namespace>\S+)'
    r'\s+tests\[(?P<tests_count>\d+)\]: (?P<tests>.+)$',
)


class Scenario(vedro.Scenario):
    subject = 'plan matches actual parallel run'

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
        self.observations_dir = temp_keeper.create_tmp_dir(prefix='uc-plan-consistency-')
        patch_env({'UC_TEST_OBSERVATIONS_DIR': str(self.observations_dir)})

    async def given_vedro_project_with_two_envs(self):
        scenarios = {}
        for index in range(4):
            name = f'env_a_{index}'
            file_name = f'test_{name}.py'
            scenarios[file_name] = SCENARIO_TEMPLATE.format(
                subject=f'env-a scenario {index}',
                env_description='env-a',
                name=name,
                file_name=file_name,
            )
        for index in range(2):
            name = f'env_b_{index}'
            file_name = f'test_{name}.py'
            scenarios[file_name] = SCENARIO_TEMPLATE.format(
                subject=f'env-b scenario {index}',
                env_description='env-b',
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
                    workers_per_env={{"env-a": 2, "env-b": 1}},
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
            args=['run', 'scenarios/', '--uc-mt', '--uc-mt-plan=1'],
        )

    async def then_plan_should_be_rendered_without_containers(self):
        assert self.plan_result.returncode == 0, self.plan_result.stdout + self.plan_result.stderr
        assert retrieve_all_docker_containers() == []
        self.planned_workers = self._parse_workers(self.plan_result.stdout)
        assert len(self.planned_workers) == 3

    async def when_actual_parallel_run_is_finished(self):
        self.run_result = await CliRunner().run_vedro(
            self.project_dir,
            args=['run', 'scenarios/', '--uc-mt'],
        )

    async def then_actual_run_should_succeed(self):
        assert self.run_result.returncode == 0, self.run_result.stdout + self.run_result.stderr

    async def and_actual_workers_namespaces_and_tests_should_match_plan(self):
        observations = {
            observation['file']: observation
            for observation in (
                json.loads(file.read_text())
                for file in self.observations_dir.glob('*.json')
            )
        }
        actual_workers = {}
        for observation in observations.values():
            worker_id = observation['worker_id']
            actual = actual_workers.setdefault(worker_id, {
                'namespace': observation['namespace'],
                'env_id': observation['env_id'],
                'tests': set(),
            })
            actual['tests'].add(observation['file'])

        assert set(actual_workers) == set(self.planned_workers)
        for worker_id, planned in self.planned_workers.items():
            actual = actual_workers[worker_id]
            assert actual['namespace'] == planned['namespace']
            assert actual['env_id'] == planned['namespace']
            assert actual['tests'] == planned['tests']

    async def and_actual_container_count_should_match_planned_replicas(self):
        containers = retrieve_all_docker_containers()
        assert len(containers) == 3

    def _parse_workers(self, stdout: str) -> dict[int, dict]:
        workers = {}
        for line in stdout.splitlines():
            match = WORKER_LINE.match(line)
            if not match:
                continue
            worker_id = int(match.group('worker_id'))
            workers[worker_id] = {
                'env': match.group('env'),
                'replica_index': int(match.group('replica')),
                'namespace': match.group('namespace'),
                'tests': {
                    Path(test.strip()).name
                    for test in match.group('tests').split(',')
                },
            }
        return workers
