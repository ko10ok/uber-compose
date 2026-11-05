import asyncio
import os
from pathlib import Path
import signal
import sys
import time

from contexts.compose_file import compose_file
from contexts.isolated_project import isolated_project
from contexts.no_docker_containers import no_docker_containers
from contexts.vedro_subprocess_project import vedro_subprocess_project
import vedro


class Scenario(vedro.Scenario):
    subject = 'run vedro with parallel workers and interrupt'

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

    async def given_vedro_project_with_slow_scenarios(self):
        scenario_template = """
import time

import vedro

from uber_compose import Environment
from uber_compose import Service


class Scenario(vedro.Scenario):
    subject = '{subject}'
    env = Environment(Service('s1'), description='{env_description}')

    def when_it_sleeps(self):
        time.sleep(60)
"""
        scenarios = {
            'test_env_a.py': scenario_template.format(
                env_description='env-a', subject='env-a slow scenario',
            ),
            'test_env_b.py': scenario_template.format(
                env_description='env-b', subject='env-b slow scenario',
            ),
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
                    env_parallelism={{"env-a": 1, "env-b": 1}},
                ),
            }}

        class UberComposeParallel(VedroUberComposeParallel):
            enabled = True
""",
            scenarios=scenarios,
        )

    async def when_vedro_is_interrupted(self):
        self.process = await asyncio.create_subprocess_exec(
            sys.executable, '-m', 'vedro', 'run', 'scenarios/',
            cwd=str(self.project_dir),
            env=os.environ.copy(),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        self.stdout_task = asyncio.create_task(self.process.stdout.read())
        self.stderr_task = asyncio.create_task(self.process.stderr.read())
        await asyncio.sleep(4)
        self.process.send_signal(signal.SIGINT)

        try:
            await asyncio.wait_for(self.process.wait(), timeout=20)
        except asyncio.TimeoutError:
            self.process.kill()
            await self.process.wait()
            raise AssertionError('parallel run did not stop after SIGINT')

    async def then_it_should_stop_with_failure_code(self):
        self.stdout = (await self.stdout_task).decode('utf-8', errors='replace')
        self.stderr = (await self.stderr_task).decode('utf-8', errors='replace')
        assert self.process.returncode != 0, self.stdout + self.stderr

    async def and_spawned_worker_processes_should_be_stopped(self):
        deadline = time.monotonic() + 10
        while True:
            leftovers = []
            for entry in Path('/proc').iterdir():
                if not entry.name.isdigit():
                    continue
                try:
                    cmdline = entry.joinpath('cmdline').read_bytes().replace(b'\0', b' ').decode(errors='replace')
                except OSError:
                    continue
                if 'vedro' in cmdline and str(self.project_dir) in cmdline:
                    leftovers.append((entry.name, cmdline.strip()))

            if not leftovers:
                return
            if time.monotonic() > deadline:
                raise AssertionError(f'worker processes are still running: {leftovers}')
            await asyncio.sleep(0.2)
