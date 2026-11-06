import json

from contexts.compose_file import compose_file
from contexts.isolated_project import isolated_project
from contexts.no_docker_containers import no_docker_containers
from contexts.no_docker_containers import retrieve_all_docker_containers
from contexts.vedro_subprocess_project import vedro_subprocess_project
from helpers.env_vars import patch_env
from interfaces.vedro_cli import CliRunner
import vedro
import vedro.plugins.temp_keeper as temp_keeper

from uber_compose.helpers.labels import Label

SCENARIO_TEMPLATE = """
import docker
import json
import os

import vedro

from uber_compose import Environment
from uber_compose import Service
from uber_compose.env_description.env_tools import singleton


class Scenario(vedro.Scenario):
    subject = '{subject}'
    env = Environment(
        singleton(Service('db')),
        Service('app'),
        description='{env_description}',
    )

    def when_singleton_identity_is_recorded(self):
        client = docker.APIClient(base_url=os.environ['DOCKER_HOST'])
        db_containers = [
            container
            for container in client.containers(all=True)
            if container.get('Labels', {{}}).get('com.docker.compose.service') == 'db'
            and container.get('Labels', {{}}).get('com.docker.compose.project') == os.environ['COMPOSE_PROJECT_NAME']
        ]
        assert len(db_containers) == 1

        observations_dir = os.environ['UC_TEST_OBSERVATIONS_DIR']
        with open(os.path.join(observations_dir, '{name}.json'), 'w') as file:
            json.dump({{
                'env': '{env_description}',
                'singleton_id': db_containers[0]['Id'],
            }}, file)
"""


class Scenario(vedro.Scenario):
    subject = 'run vedro with max_concurrent_envs equal to one and singleton service'

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

  app:
    image: busybox:stable
    command: 'sh -c "trap : TERM INT; sleep 604800; wait"'
"""
        )

    async def given_observations_directory(self):
        self.observations_dir = temp_keeper.create_tmp_dir(prefix='uc-singleton-rotation-')
        patch_env({'UC_TEST_OBSERVATIONS_DIR': str(self.observations_dir)})

    async def given_vedro_project_with_two_envs(self):
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
                    max_concurrent_envs=1,
                ),
            }}
""",
            scenarios={
                'test_env_a.py': SCENARIO_TEMPLATE.format(
                    subject='env-a scenario runs before rotation',
                    env_description='env-a',
                    name='env_a',
                ),
                'test_env_b.py': SCENARIO_TEMPLATE.format(
                    subject='env-b scenario runs after rotation',
                    env_description='env-b',
                    name='env_b',
                ),
            },
        )

    async def when_vedro_is_run_with_two_envs_sequentially(self):
        self.run_result = await CliRunner().run_vedro(self.project_dir, args=['run', 'scenarios/'])

    async def then_it_should_exit_with_code_zero(self):
        assert self.run_result.returncode == 0, self.run_result.stdout + self.run_result.stderr

    async def and_it_should_record_singleton_identity_in_both_envs(self):
        self.observations = {
            file.stem: json.loads(file.read_text())
            for file in self.observations_dir.glob('*.json')
        }
        assert set(self.observations) == {'env_a', 'env_b'}

    async def and_it_should_not_restart_the_singleton_between_envs(self):
        singleton_ids = {
            observation['singleton_id']
            for observation in self.observations.values()
        }
        assert len(singleton_ids) == 1

    async def and_it_should_leave_only_the_last_env_services_running(self):
        containers = retrieve_all_docker_containers()
        app_containers = [
            container for container in containers
            if container.get('Labels', {}).get(Label.TEMPLATE_SERVICE_NAME) == 'app'
        ]
        db_containers = [
            container for container in containers
            if container.get('Labels', {}).get(Label.TEMPLATE_SERVICE_NAME) == 'db'
        ]
        assert len(app_containers) == 1
        assert len(db_containers) == 1
