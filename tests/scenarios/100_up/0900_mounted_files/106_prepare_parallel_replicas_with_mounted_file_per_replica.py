from pathlib import Path

from contexts.compose_file import compose_file
from contexts.isolated_project import isolated_constants
from contexts.isolated_project import isolated_project
from contexts.mounted_file import mounted_template
from contexts.no_docker_containers import no_docker_containers
from contexts.no_docker_containers import retrieve_all_docker_containers
from d42 import schema
from schemas.docker import ContainerSchema
import vedro

from uber_compose import Environment
from uber_compose import Service
from uber_compose.uber_compose import UberCompose


class Scenario(vedro.Scenario):
    subject = 'prepare parallel replicas with mounted file per replica'

    async def given_no_docker_containers(self):
        no_docker_containers()

    async def given_isolated_project(self):
        self.project = isolated_project()
        self.instance_files_root = self.project.tmp_envs_path
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

    async def given_mounted_template(self):
        self.template_path = mounted_template(
            'env: [[namespace]]\nservice: [[s1]]\n'
        )
        self.target_path = '/app/config.yaml'

    async def given_env_with_mounted_file(self):
        self.environment = Environment(
            Service(
                's1',
                mounted_files=(f'{self.template_path}:{self.target_path}',),
            ),
            description='env-a',
        )

    async def when_user_prepares_two_replicas(self):
        self.ready_envs = await UberCompose(
            cfg_constants=self.constants,
        ).prepare_parallel_environments(
            config_templates=[self.environment],
            compose_files=self.compose_files,
            workers_per_env={'env-a': 2},
        )

    async def then_each_replica_should_have_its_own_rendered_file(self):
        assert len(self.ready_envs) == 2
        assert len({ready_env.env_id for ready_env in self.ready_envs}) == 2
        replica_0 = self.ready_envs[0]
        replica_1 = self.ready_envs[1]
        replica_0_source = Path.cwd() / 'e2e_mounted_files' / replica_0.env_id / self.template_path
        replica_1_source = Path.cwd() / 'e2e_mounted_files' / replica_1.env_id / self.template_path
        assert replica_0_source.read_text() == (
            f'env: {replica_0.env_id}\n'
            f'service: s1-{replica_0.env_id}\n'
        )
        assert replica_1_source.read_text() == (
            f'env: {replica_1.env_id}\n'
            f'service: s1-{replica_1.env_id}\n'
        )

    async def and_each_replica_should_mount_its_own_rendered_file(self):
        replica_0 = self.ready_envs[0]
        replica_1 = self.ready_envs[1]
        replica_0_source = Path.cwd() / 'e2e_mounted_files' / replica_0.env_id / self.template_path
        replica_1_source = Path.cwd() / 'e2e_mounted_files' / replica_1.env_id / self.template_path
        containers = retrieve_all_docker_containers()
        assert containers == schema.list([
            ...,
            ContainerSchema % {
                'Labels': {
                    'com.docker.compose.service': f's1-{replica_0.env_id}',
                },
                'Mounts': [
                    {
                        'Source': str(replica_0_source),
                        'Destination': self.target_path,
                    },
                ],
            },
            ...,
        ])
        assert containers == schema.list([
            ...,
            ContainerSchema % {
                'Labels': {
                    'com.docker.compose.service': f's1-{replica_1.env_id}',
                },
                'Mounts': [
                    {
                        'Source': str(replica_1_source),
                        'Destination': self.target_path,
                    },
                ],
            },
            ...,
        ])
