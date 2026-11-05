from contexts.compose_file import compose_file
from contexts.isolated_project import isolated_project
from contexts.no_docker_containers import no_docker_containers
from contexts.no_docker_containers import retrieve_all_docker_containers
from contexts.vedro_subprocess_project import vedro_subprocess_project
from interfaces.vedro_cli import CliRunner
import vedro

from uber_compose import Environment
from uber_compose import Service
from uber_compose.core.utils.compose_instance_cfg import get_stable_env_id
from uber_compose.helpers.labels import Label


class Scenario(vedro.Scenario):
    subject = 'run vedro with uc enabled and env_parallelism'

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

    async def given_env_template(self):
        self.environment = Environment(Service('s1'), description='env-a')

    async def given_vedro_project_with_env_parallelism(self):
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
                    env_parallelism={{"env-a": 2}},
                    default_env_parallelism=1,
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

    async def when_vedro_is_run_with_just_up(self):
        self.run_result = await CliRunner().run_vedro(
            self.project_dir, args=['run', 'scenarios/', '--uc-ju']
        )

    async def then_it_should_exit_with_code_zero(self):
        assert self.run_result.returncode == 0, self.run_result.stdout + self.run_result.stderr

    async def and_it_should_start_configured_number_of_replicas(self):
        expected_env_ids = {
            get_stable_env_id(self.environment, 0),
            get_stable_env_id(self.environment, 1),
        }
        self.containers = retrieve_all_docker_containers()
        assert len(self.containers) == 2
        assert {
            container.get('Labels', {}).get(Label.ENV_ID)
            for container in self.containers
        } == expected_env_ids
        assert {
            container.get('Labels', {}).get('com.docker.compose.service')
            for container in self.containers
        } == {f's1-{env_id}' for env_id in expected_env_ids}
