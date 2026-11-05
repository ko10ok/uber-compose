from contexts.compose_file import compose_file
from contexts.isolated_project import isolated_project
from contexts.no_docker_containers import no_docker_containers
from contexts.no_docker_containers import retrieve_all_docker_containers
from contexts.no_docker_containers import stopped_docker_container
from contexts.vedro_subprocess_project import vedro_subprocess_project
from interfaces.vedro_cli import CliRunner
import vedro

from uber_compose.helpers.labels import Label


class Scenario(vedro.Scenario):
    subject = 'run vedro with uc enabled and workers_per_env after one replica container is gone'

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

    async def given_vedro_project_with_two_replicas(self):
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


class Scenario(vedro.Scenario):
    subject = 'env-a scenario'
    env = Environment(Service('s1'), description='env-a')

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
        assert len(self.first_containers) == 2
        self.second_replica = self._container_for_slot(self.first_containers, 'w1')
        self.first_replica = self._container_for_slot(self.first_containers, 'w0')

    async def given_second_replica_container_is_removed(self):
        service_name = self.second_replica.get('Labels', {}).get('com.docker.compose.service')
        stopped_docker_container(service_name)
        remaining = retrieve_all_docker_containers()
        assert len(remaining) == 1

    async def when_vedro_is_rerun_with_the_same_replica_count(self):
        self.second_run = await CliRunner().run_vedro(
            self.project_dir, args=['run', 'scenarios/', '--uc-ju']
        )

    async def then_it_should_exit_with_code_zero(self):
        assert self.second_run.returncode == 0, self.second_run.stdout + self.second_run.stderr

    async def and_it_should_recreate_the_missing_replica_with_same_env_id(self):
        self.second_containers = retrieve_all_docker_containers()
        assert len(self.second_containers) == 2
        recreated = self._container_for_slot(self.second_containers, 'w1')
        assert recreated.get('Labels', {}).get(Label.ENV_ID) == \
            self.second_replica.get('Labels', {}).get(Label.ENV_ID)
        assert recreated['Id'] != self.second_replica['Id']

    async def and_it_should_not_recreate_the_kept_replica(self):
        kept = self._container_for_slot(self.second_containers, 'w0')
        assert kept['Id'] == self.first_replica['Id']

    @staticmethod
    def _container_for_slot(containers, slot):
        for container in containers:
            service_name = container.get('Labels', {}).get('com.docker.compose.service', '')
            if service_name.startswith(f's1-{slot}-'):
                return container
        raise AssertionError(f'No container for slot {slot}')
