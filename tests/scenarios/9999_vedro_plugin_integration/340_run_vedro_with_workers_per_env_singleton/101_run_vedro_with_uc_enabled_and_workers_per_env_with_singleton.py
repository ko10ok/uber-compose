from contexts.compose_file import compose_file
from contexts.isolated_project import isolated_project
from contexts.no_docker_containers import no_docker_containers
from contexts.no_docker_containers import retrieve_all_docker_containers
from contexts.vedro_subprocess_project import vedro_subprocess_project
from interfaces.vedro_cli import CliRunner
import vedro

from uber_compose.helpers.labels import Label


class Scenario(vedro.Scenario):
    subject = 'run vedro with uc enabled and workers_per_env replicas with a singleton service'

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
  db:
    image: busybox:stable
    command: 'sh -c "trap : TERM INT; sleep 604800; wait"'

  s1:
    image: busybox:stable
    command: 'sh -c "trap : TERM INT; sleep 604800; wait"'
"""
        )

    async def given_vedro_project_with_singleton_and_two_replicas(self):
        self.project_dir = vedro_subprocess_project(
            vedro_cfg=f"""
import vedro

from uber_compose import ComposeConfig
from uber_compose import DEFAULT_COMPOSE
from uber_compose import VedroUberCompose


class Config(vedro.Config):
    class Plugins(vedro.Config.Plugins):
        class UberCompose(VedroUberCompose):
            enabled = True
            compose_cfgs = {{
                DEFAULT_COMPOSE: ComposeConfig(
                    compose_files="{self.compose_filename}",
                    workers_per_env={{"env-a": 2}},
                ),
            }}
""",
            scenarios={
                'test_env_a.py': """
import vedro

from uber_compose import Environment
from uber_compose import Service
from uber_compose.env_description.env_types import ServiceMode


class Scenario(vedro.Scenario):
    subject = 'env-a scenario'
    env = Environment(
        Service('db', mode=ServiceMode.SINGLETON),
        Service('s1'),
        description='env-a',
    )

    def when_nothing_special_happens(self):
        self.result = 'ok'

    def then_it_should_just_pass(self):
        assert self.result == 'ok'
"""
            },
        )

    async def when_vedro_is_run_with_just_up(self):
        self.run_result = await CliRunner().run_vedro(
            self.project_dir, args=['run', 'scenarios/', '--uc-ju']
        )

    async def then_it_should_exit_with_code_zero(self):
        assert self.run_result.returncode == 0, self.run_result.stdout + self.run_result.stderr

    async def and_it_should_start_single_singleton_and_two_replicas_of_other_service(self):
        self.containers = retrieve_all_docker_containers()
        singleton_containers = [
            container for container in self.containers
            if container.get('Labels', {}).get(Label.TEMPLATE_SERVICE_NAME) == 'db'
        ]
        replica_containers = [
            container for container in self.containers
            if container.get('Labels', {}).get(Label.TEMPLATE_SERVICE_NAME) == 's1'
        ]
        assert len(singleton_containers) == 1
        assert len(replica_containers) == 2
