from contexts.compose_file import compose_file
from contexts.isolated_project import isolated_constants
from contexts.isolated_project import isolated_project
from contexts.no_docker_containers import no_docker_containers
from contexts.services_started import services_started
from helpers.benchmark import measure_async
from helpers.benchmark import parallel_load_factor
import vedro

from uber_compose import CommonJsonCli
from uber_compose import Environment
from uber_compose import Service
from uber_compose.uber_compose import UberCompose

ITERATIONS = 10
WARMUP_ITERATIONS = 1
MEDIAN_THRESHOLD_S = 2.0
P95_THRESHOLD_S = 4.0
LOAD_FACTOR = parallel_load_factor()


class Scenario(vedro.Scenario):
    subject = 'exec through CommonJsonCli benchmark fits thresholds'

    async def given_no_docker_containers(self):
        no_docker_containers()

    async def given_isolated_project(self):
        self.project = isolated_project()
        self.constants = isolated_constants(self.project)

    async def given_compose_file(self):
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

    async def given_service_started(self):
        await services_started(
            constants=self.constants,
            compose_files=self.compose_files,
            config_template=Environment(Service('s1'), description='benchmark'),
        )

    async def when_user_execs_via_common_json_cli_repeatedly(self):
        self.json_cli = CommonJsonCli(cli_client=UberCompose(cfg_constants=self.constants))
        self.command = 'echo {\\"level\\": \\"stdout\\", \\"benchmark\\": true}'

        async def exec_once():
            response = await self.json_cli.exec(
                container='s1',
                command=self.command,
            )
            assert response.stdout == ['{"level": "stdout", "benchmark": true}']

        self.stats = await measure_async(
            exec_once,
            iterations=ITERATIONS,
            warmup=WARMUP_ITERATIONS,
        )
        print(f'exec CommonJsonCli benchmark: {self.stats.describe()}')

    async def then_median_exec_time_should_fit_threshold(self):
        assert self.stats.median_s <= MEDIAN_THRESHOLD_S * LOAD_FACTOR, (
            f'Median exec time {self.stats.median_s:.3f}s exceeds '
            f'{MEDIAN_THRESHOLD_S * LOAD_FACTOR:.3f}s: {self.stats.describe()}'
        )

    async def then_p95_exec_time_should_fit_threshold(self):
        assert self.stats.p95_s <= P95_THRESHOLD_S * LOAD_FACTOR, (
            f'P95 exec time {self.stats.p95_s:.3f}s exceeds '
            f'{P95_THRESHOLD_S * LOAD_FACTOR:.3f}s: {self.stats.describe()}'
        )
