from contexts.compose_file import compose_file
from contexts.isolated_project import isolated_project
from contexts.no_docker_containers import no_docker_containers
from contexts.no_docker_containers import retrieve_all_docker_containers
from contexts.vedro_subprocess_project import vedro_subprocess_project
from helpers.env_vars import patch_env
from interfaces.vedro_cli import CliRunner
import vedro

from uber_compose import Environment
from uber_compose import Service
from uber_compose import env_group_key_for
from uber_compose.helpers.labels import Label


class Scenario(vedro.Scenario):
    subject = 'run vedro with uc and parallel plugins enabled as a worker for one env group'

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

  s2:
    image: busybox:stable
    command: 'sh -c "trap : TERM INT; sleep 604800; wait"'
"""
        )

    async def given_vedro_project_with_both_plugins_and_two_envs(self):
        self.env_a_subject = 'env-a scenario for this worker'
        self.env_b_subject = 'env-b scenario for another worker'
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
                DEFAULT_COMPOSE: ComposeConfig(compose_files="{self.compose_filename}"),
            }}

        class UberComposeParallel(VedroUberComposeParallel):
            enabled = True
""",
            scenarios={
                'test_env_a.py': f"""
import vedro

from uber_compose import Environment
from uber_compose import Service


class Scenario(vedro.Scenario):
    subject = '{self.env_a_subject}'
    env = Environment(Service('s1'), description='env-a')

    def when_nothing_special_happens(self):
        self.result = 'ok'

    def then_it_should_just_pass(self):
        assert self.result == 'ok'
""",
                'test_env_b.py': f"""
import vedro

from uber_compose import Environment
from uber_compose import Service


class Scenario(vedro.Scenario):
    subject = '{self.env_b_subject}'
    env = Environment(Service('s2'), description='env-b')

    def when_nothing_special_happens(self):
        self.result = 'ok'

    def then_it_should_just_pass(self):
        assert self.result == 'ok'
""",
            },
        )

    async def given_worker_is_assigned_to_env_a_group(self):
        env_a = Environment(Service('s1'), description='env-a')
        patch_env({
            'UC_WORKER_ID': '0',
            'UC_WORKERS_TOTAL': '2',
            'UC_WORKER_GROUPS': env_group_key_for(env_a),
            'UC_NAMESPACE_MAP': '{}',
        })

    async def when_vedro_is_run_in_worker_mode(self):
        self.run_result = await CliRunner().run_vedro(self.project_dir, args=['run', 'scenarios/'])

    async def then_it_should_exit_with_code_zero(self):
        assert self.run_result.returncode == 0, self.run_result.stdout + self.run_result.stderr

    async def and_it_should_run_only_the_assigned_env_scenario(self):
        assert self.env_a_subject in self.run_result.stdout
        assert self.env_b_subject not in self.run_result.stdout

    async def and_it_should_start_only_the_assigned_env_services(self):
        self.containers = retrieve_all_docker_containers()
        assert len(self.containers) == 1
        labels = self.containers[0].get('Labels', {})
        assert labels.get('com.docker.compose.service', '').startswith('s1-w0-')
        assert labels.get(Label.ENV_DESCRIPTION) == 'env-a'
