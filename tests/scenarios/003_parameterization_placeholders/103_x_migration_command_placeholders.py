from contexts.compose_file import compose_file
from contexts.isolated_project import isolated_constants
from contexts.isolated_project import isolated_project
from contexts.no_docker_containers import no_docker_containers
from helpers.docker_migration_result import get_file_from_container
from helpers.env_vars import patch_env
from rtry import retry
import vedro

from uber_compose import Environment
from uber_compose import Service
from uber_compose.uber_compose import UberCompose


class Scenario(vedro.Scenario):
    subject = 'use service names env id worker and run id in x-migration commands'

    async def given_no_docker_containers(self):
        no_docker_containers()

    async def given_isolated_project(self):
        self.project = isolated_project()
        self.instance_files_root = self.project.tmp_envs_path
        self.constants = isolated_constants(self.project)

    async def given_compose_file_with_templated_migration(self):
        self.compose_files = 'docker-compose.yaml'
        self.migration_result_file = '/tmp/placeholders.log'
        compose_file(
            self.compose_files,
            content="""
version: "3"

services:
  s1:
    image: busybox:stable
    command: 'sh -c "trap : TERM INT; sleep 604800; wait"'
    x-migration:
      - after_start: >
          sh -c 'echo
          "[[env_id]]|[[worker_id]]|[[namespace]]|[[s1]]|[[test_run_id]]|[[worker_id_alpha_numeric]]|[[namespace_alpha_numeric]]|[[worker_id_alpha_numeric_6]]|[[namespace_alpha_numeric_6]]"
          > /tmp/placeholders.log'
"""
        )

    async def given_worker_environment(self):
        patch_env({
            'UC_WORKER_ID': '1',
            'UC_WORKERS_TOTAL': '2',
        })

    async def when_user_up_env_with_explicit_env_id_and_run_id(self):
        self.env_id = 'w1-mig'
        self.run_id = 'run-mig'
        self.response = await UberCompose(
            cfg_constants=self.constants,
            run_id=self.run_id,
        ).up(
            compose_files=self.compose_files,
            config_template=Environment(Service('s1'), description='env-a'),
            parallelism_limit=2,
            env_id=self.env_id,
        )

    @retry(attempts=3, delay=1)
    async def then_migration_placeholders_should_be_substituted(self):
        content = get_file_from_container('s1-w1-mig', self.migration_result_file)
        assert content == b'w1-mig|1|w1-mig|s1-w1-mig|run-mig|w1|w1mig|pzsttk|kuntur\n'
