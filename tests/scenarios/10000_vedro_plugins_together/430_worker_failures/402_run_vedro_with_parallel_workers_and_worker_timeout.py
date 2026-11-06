from contexts.compose_file import compose_file
from contexts.isolated_project import isolated_project
from contexts.no_docker_containers import no_docker_containers
from contexts.vedro_subprocess_project import vedro_subprocess_project
from interfaces.vedro_cli import CliRunner
import vedro


class Scenario(vedro.Scenario):
    subject = 'run vedro with parallel workers and worker timeout'

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

    async def given_vedro_project_with_hanging_and_passing_workers(self):
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
            worker_timeout = 20
""",
            scenarios={
                'test_env_a.py': """
import time

import vedro

from uber_compose import Environment
from uber_compose import Service


class Scenario(vedro.Scenario):
    subject = 'env-a scenario hangs'
    env = Environment(Service('s1'), description='env-a')

    def when_it_hangs(self):
        time.sleep(60)
""",
                'test_env_b.py': """
import vedro

from uber_compose import Environment
from uber_compose import Service


class Scenario(vedro.Scenario):
    subject = 'env-b scenario finishes before the timeout'
    env = Environment(Service('s1'), description='env-b')

    def when_nothing_special_happens(self):
        self.result = 'ok'

    def then_it_should_pass(self):
        assert self.result == 'ok'
"""
            },
        )

    async def when_vedro_is_run(self):
        self.run_result = await CliRunner().run_vedro(self.project_dir, args=['run', 'scenarios/', '--uc-mt'])

    async def then_it_should_finish_with_failure_code(self):
        assert self.run_result.returncode != 0, self.run_result.stdout + self.run_result.stderr

    async def and_it_should_report_the_surviving_worker_result(self):
        assert 'env-b scenario finishes before the timeout' in self.run_result.stdout
        assert '2 scenarios, 1 passed, 1 failed' in self.run_result.stdout

    async def and_it_should_report_the_hung_worker_as_timed_out(self):
        assert 'env-a scenario hangs' in self.run_result.stdout
        assert 'timed out' in self.run_result.stdout
