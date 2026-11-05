import json

from contexts.compose_file import compose_file
from contexts.isolated_project import isolated_project
from contexts.no_docker_containers import no_docker_containers
from contexts.vedro_subprocess_project import vedro_subprocess_project
from helpers.env_vars import patch_env
from interfaces.vedro_cli import CliRunner
import vedro
import vedro.plugins.temp_keeper as temp_keeper


class Scenario(vedro.Scenario):
    subject = 'run vedro with parallel workers and worker concurrency limit'

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

    async def given_concurrency_observations_directory(self):
        self.observations_dir = temp_keeper.create_tmp_dir(prefix='uc-concurrency-')
        patch_env({'UC_CONCURRENCY_DIR': str(self.observations_dir)})

    async def given_vedro_project_with_four_replicas_and_limit(self):
        scenario_template = """
import json
import os
import time

import vedro

from uber_compose import Environment
from uber_compose import Service


class Scenario(vedro.Scenario):
    subject = 'env-a scenario {index}'
    env = Environment(Service('s1'), description='env-a')

    def when_it_runs(self):
        started_at = time.time()
        time.sleep(2)
        ended_at = time.time()
        observations_dir = os.environ['UC_CONCURRENCY_DIR']
        with open(os.path.join(observations_dir, '{index}.json'), 'w') as file:
            json.dump({{'start': started_at, 'end': ended_at}}, file)
"""
        scenarios = {
            f'test_env_a_{index}.py': scenario_template.format(index=index)
            for index in range(4)
        }
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
                    env_parallelism={{"env-a": 4}},
                ),
            }}

        class UberComposeParallel(VedroUberComposeParallel):
            enabled = True
            worker_concurrency = 2
""",
            scenarios=scenarios,
        )

    async def when_vedro_is_run(self):
        self.run_result = await CliRunner().run_vedro(self.project_dir, args=['run', 'scenarios/'])

    async def then_it_should_exit_with_code_zero(self):
        assert self.run_result.returncode == 0, self.run_result.stdout + self.run_result.stderr

    async def and_it_should_not_run_more_workers_than_the_limit(self):
        intervals = [
            json.loads(file.read_text())
            for file in self.observations_dir.glob('*.json')
        ]
        assert len(intervals) == 4

        events = []
        for interval in intervals:
            events.append((interval['start'], 1))
            events.append((interval['end'], -1))
        events.sort(key=lambda item: (item[0], item[1]))

        active = 0
        max_active = 0
        for _, delta in events:
            active += delta
            max_active = max(max_active, active)

        assert max_active <= 2
