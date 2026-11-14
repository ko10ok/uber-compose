from contexts.compose_file import compose_file
from contexts.isolated_project import isolated_constants
from contexts.isolated_project import isolated_project
from contexts.no_docker_containers import no_docker_containers
from d42 import schema
from helpers.benchmark import measure_async
from helpers.benchmark import parallel_load_factor
import vedro

from uber_compose.env_description.env_types import Environment
from uber_compose.env_description.env_types import Service
from uber_compose.uber_compose import UberCompose

ITERATIONS = 5
WARMUP_ITERATIONS = 1
MEDIAN_THRESHOLD_S = 5.0
P95_THRESHOLD_S = 8.0
LOAD_FACTOR = parallel_load_factor()


class Scenario(vedro.Scenario):
    subject = 'up services startup benchmark fits thresholds'

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

    async def when_user_ups_env_repeatedly(self):
        self.uber_compose = UberCompose(cfg_constants=self.constants)
        self.env_counter = 0

        async def up_once():
            self.env_counter += 1
            response = await self.uber_compose.up(
                compose_files=self.compose_files,
                config_template=Environment(Service('s1'), description='benchmark'),
                parallelism_limit=2,
                env_id=f'bench-{self.env_counter}',
            )
            assert response.env_id == schema.str

        self.stats = await measure_async(
            up_once,
            iterations=ITERATIONS,
            warmup=WARMUP_ITERATIONS,
        )
        print(f'up services benchmark: {self.stats.describe()}')

    async def then_median_startup_time_should_fit_threshold(self):
        assert self.stats.median_s <= MEDIAN_THRESHOLD_S * LOAD_FACTOR, (
            f'Median startup time {self.stats.median_s:.3f}s exceeds '
            f'{MEDIAN_THRESHOLD_S * LOAD_FACTOR:.3f}s: {self.stats.describe()}'
        )

    async def then_p95_startup_time_should_fit_threshold(self):
        assert self.stats.p95_s <= P95_THRESHOLD_S * LOAD_FACTOR, (
            f'P95 startup time {self.stats.p95_s:.3f}s exceeds '
            f'{P95_THRESHOLD_S * LOAD_FACTOR:.3f}s: {self.stats.describe()}'
        )
