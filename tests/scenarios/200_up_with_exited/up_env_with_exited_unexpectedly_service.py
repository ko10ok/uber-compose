import vedro
from d42 import schema
from uber_compose import Environment
from uber_compose import Service

from contexts.compose_file import compose_file
from contexts.no_docker_compose_files import no_docker_compose_files
from contexts.no_docker_containers import no_docker_containers
from contexts.no_docker_containers import retrieve_all_docker_containers
from schemas.docker import ContainerSchema
from uber_compose import UberCompose


class Scenario(vedro.Scenario):
    async def no_docker_containers(self):
        no_docker_containers()

    async def no_docker_copose_files(self):
        no_docker_compose_files()

    async def given_compose_file_with_service_with_migration(self):
        self.compose_filename = 'docker-compose.basic.yaml'
        self.migration_result_file = '/tmp/migration.log'
        compose_file(
            self.compose_filename,
            content="""
version: "3"

services:
  s1:
    image: busybox:stable
    command: 'sh -c "exit 10"'
"""
        )

    async def when_user_up_env_with_unexpected_to_exit_service(self):
        self.response = await UberCompose().up(
            config_template=Environment(
                'DEFAULT',
                Service('s1')
            ),
            compose_files='docker-compose.basic.yaml'
        )

    async def then_it_should_not_up_env(self):
        self.containers = retrieve_all_docker_containers()
        assert self.containers == schema.list([
            ContainerSchema % {
                'State': 'exited',
                'Labels': {
                    'com.docker.compose.service': 's1',
                    'com.docker.compose.project.config_files': f'/tmp-envs/no_id/{self.compose_filename}',
                },
            },
        ])
        assert 'Exited (10)' in self.containers[0]['Status']

    async def then_it_should_out_services_logs(self):
        self.response_json = self.response.json()
        assert self.response_json == schema.dict({'error': schema.str})
        assert "Can't up services" in self.response_json['error']
        assert "s1" in self.response_json['error']
        assert "exited" in self.response_json['error']
