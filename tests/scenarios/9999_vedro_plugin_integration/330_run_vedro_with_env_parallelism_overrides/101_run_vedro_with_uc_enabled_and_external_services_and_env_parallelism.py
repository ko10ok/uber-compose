from contexts.compose_file import compose_file
from contexts.isolated_project import isolated_project
from contexts.no_docker_containers import no_docker_containers
from contexts.no_docker_containers import retrieve_all_docker_containers
from contexts.vedro_subprocess_project import vedro_subprocess_project
from interfaces.vedro_cli import CliRunner
import vedro

from uber_compose.helpers.labels import Label


class Scenario(vedro.Scenario):
    subject = 'run vedro with uc enabled and uc_external_services ALL and env_parallelism replicas'

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

  ext:
    image: busybox:stable
    command: 'sh -c "trap : TERM INT; sleep 604800; wait"'
"""
        )

    async def given_vedro_project_with_overridden_service_and_two_replicas(self):
        self.project_dir = vedro_subprocess_project(
            vedro_cfg=f"""
import vedro

from uber_compose import ComposeConfig
from uber_compose import DEFAULT_COMPOSE
from uber_compose import Env
from uber_compose import OverridenService
from uber_compose import Service
from uber_compose import VedroUberCompose


class Config(vedro.Config):
    class Plugins(vedro.Config.Plugins):
        class UberCompose(VedroUberCompose):
            enabled = True
            compose_cfgs = {{
                DEFAULT_COMPOSE: ComposeConfig(
                    compose_files="{self.compose_filename}",
                    env_parallelism={{"env-a": 2}},
                    overridden_services=[
                        OverridenService(
                            Service("ext"),
                            services_envs_fix=[
                                Service("s1", env=Env({{"EXT_URL": "http://ext"}})),
                            ],
                        ),
                    ],
                ),
            }}
""",
            scenarios={
                'test_env_a.py': """
import os

import vedro

from uber_compose import Environment
from uber_compose import Service


class Scenario(vedro.Scenario):
    subject = 'env-a scenario'
    env = Environment(Service('s1'), Service('ext'), description='env-a')

    def then_it_should_have_external_service_env(self):
        assert os.environ['EXT_URL'] == 'http://ext'
"""
            },
        )

    async def when_vedro_is_run_with_just_up_and_external_services(self):
        self.run_result = await CliRunner().run_vedro(
            self.project_dir,
            args=['run', 'scenarios/', '--uc-ju', '--uc-external-services', 'ALL'],
        )

    async def then_it_should_exit_with_code_zero(self):
        assert self.run_result.returncode == 0, self.run_result.stdout + self.run_result.stderr

    async def and_it_should_start_two_s1_replicas_without_external_service(self):
        self.containers = retrieve_all_docker_containers()
        assert len(self.containers) == 2
        service_names = {
            container.get('Labels', {}).get('com.docker.compose.service')
            for container in self.containers
        }
        assert any(name.startswith('s1-w0-') for name in service_names)
        assert any(name.startswith('s1-w1-') for name in service_names)
        assert all(
            container.get('Labels', {}).get(Label.TEMPLATE_SERVICE_NAME) != 'ext'
            for container in self.containers
        )
