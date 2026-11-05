from contexts.compose_file import compose_file
from contexts.isolated_project import isolated_project
from contexts.no_docker_containers import no_docker_containers
from contexts.no_docker_containers import retrieve_all_docker_containers
from contexts.vedro_subprocess_project import vedro_subprocess_project
from interfaces.vedro_cli import CliRunner
import vedro

from uber_compose.helpers.labels import Label


class Scenario(vedro.Scenario):
    subject = 'run vedro twice with uc enabled and decreased workers_per_env with a singleton service'

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
            vedro_cfg=self._vedro_cfg(replicas=2),
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

    async def given_two_replicas_are_started(self):
        self.first_run = await CliRunner().run_vedro(
            self.project_dir, args=['run', 'scenarios/', '--uc-ju']
        )
        assert self.first_run.returncode == 0, self.first_run.stdout + self.first_run.stderr
        self.first_containers = retrieve_all_docker_containers()
        self.first_singleton = [
            container for container in self.first_containers
            if container.get('Labels', {}).get(Label.TEMPLATE_SERVICE_NAME) == 'db'
        ]
        assert len(self.first_singleton) == 1
        self.first_singleton_id = self.first_singleton[0]['Id']

    async def when_vedro_is_rerun_with_one_replica(self):
        (self.project_dir / 'vedro.cfg.py').write_text(self._vedro_cfg(replicas=1))
        self.second_run = await CliRunner().run_vedro(
            self.project_dir, args=['run', 'scenarios/', '--uc-ju']
        )

    async def then_it_should_exit_with_code_zero(self):
        assert self.second_run.returncode == 0, self.second_run.stdout + self.second_run.stderr

    async def and_it_should_keep_the_same_singleton_container(self):
        self.second_containers = retrieve_all_docker_containers()
        second_singleton = [
            container for container in self.second_containers
            if container.get('Labels', {}).get(Label.TEMPLATE_SERVICE_NAME) == 'db'
        ]
        assert len(second_singleton) == 1
        assert second_singleton[0]['Id'] == self.first_singleton_id

    async def and_it_should_keep_only_the_first_replica(self):
        replica_containers = [
            container for container in self.second_containers
            if container.get('Labels', {}).get(Label.TEMPLATE_SERVICE_NAME) == 's1'
        ]
        assert len(replica_containers) == 1
        service_name = replica_containers[0].get('Labels', {}).get('com.docker.compose.service')
        assert service_name.startswith('s1-w0-')

    def _vedro_cfg(self, replicas: int) -> str:
        return f"""
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
                    workers_per_env={{"env-a": {replicas}}},
                ),
            }}
"""
