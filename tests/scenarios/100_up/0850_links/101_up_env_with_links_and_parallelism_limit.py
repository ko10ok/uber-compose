from contexts.compose_file import compose_file
from contexts.isolated_project import isolated_constants
from contexts.isolated_project import isolated_project
from contexts.no_docker_containers import no_docker_containers
from contexts.no_docker_containers import retrieve_all_docker_containers
from d42 import schema
from schemas.docker import ContainerSchema
import vedro

from uber_compose import Environment
from uber_compose import Service
from uber_compose.core.utils.compose_files import read_dc_file
from uber_compose.helpers.labels import Label
from uber_compose.uber_compose import UberCompose


class Scenario(vedro.Scenario):
    subject = 'up env with links and parallelism limit'

    async def given_no_docker_containers(self):
        no_docker_containers()

    async def given_isolated_project(self):
        self.project = isolated_project()
        self.instance_files_root = self.project.tmp_envs_path
        self.constants = isolated_constants(self.project)

    async def given_compose_files_with_links(self):
        self.compose_files = 'docker-compose.yaml'
        compose_file(
            self.compose_files,
            content="""
version: "3"

services:
  cache:
    image: busybox:stable
    command: 'sh -c "trap : TERM INT; sleep 604800; wait"'
    links:
      - redis
      - db:database

  redis:
    image: busybox:stable
    command: 'sh -c "trap : TERM INT; sleep 604800; wait"'

  db:
    image: busybox:stable
    command: 'sh -c "trap : TERM INT; sleep 604800; wait"'
"""
        )

    async def given_env_template(self):
        self.environment = Environment(
            Service('cache'),
            Service('redis'),
            Service('db'),
            description='env-a',
        )

    async def when_user_up_env_with_links_and_parallelism_limit(self):
        self.env_id = 'w0-b101'
        self.response = await UberCompose(
            cfg_constants=self.constants,
        ).up(
            compose_files=self.compose_files,
            config_template=self.environment,
            parallelism_limit=2,
            env_id=self.env_id,
        )

    async def then_it_should_up_services_with_namespaced_names(self):
        self.containers = retrieve_all_docker_containers()
        assert self.containers == schema.list([
            ...,
            ContainerSchema % {
                'Labels': {
                    'com.docker.compose.service': f'cache-{self.env_id}',
                    Label.ENV_ID: self.env_id,
                    Label.ENV_DESCRIPTION: str(self.environment),
                },
            },
            ...,
        ])
        assert self.containers == schema.list([
            ...,
            ContainerSchema % {
                'Labels': {
                    'com.docker.compose.service': f'redis-{self.env_id}',
                    Label.ENV_ID: self.env_id,
                    Label.ENV_DESCRIPTION: str(self.environment),
                },
            },
            ...,
        ])
        assert self.containers == schema.list([
            ...,
            ContainerSchema % {
                'Labels': {
                    'com.docker.compose.service': f'db-{self.env_id}',
                    Label.ENV_ID: self.env_id,
                    Label.ENV_DESCRIPTION: str(self.environment),
                },
            },
            ...,
        ])

    async def and_it_should_rename_links_in_instance_compose_file(self):
        instance_compose_file = self.instance_files_root / self.env_id / self.compose_files
        dc_cfg = read_dc_file(instance_compose_file)

        def service_schema(service_name, **extra):
            return schema.dict({
                'image': schema.str('busybox:stable'),
                'command': schema.str('sh -c "trap : TERM INT; sleep 604800; wait"'),
                'environment': schema.list([]),
                'networks': schema.list([]),
                'labels': schema.dict({
                    Label.ENV_ID: schema.str(self.env_id),
                    Label.ENV_DESCRIPTION: schema.str(str(self.environment)),
                    Label.RELEASE_ID: schema.str,
                    Label.COMPOSE_FILES: schema.str(self.compose_files),
                    Label.COMPOSE_FILES_INSTANCE: schema.str(str(instance_compose_file)),
                    Label.ENV_CONFIG_TEMPLATE: schema.str,
                    Label.ENV_CONFIG_DESCRIPTION: schema.str(str(self.environment)),
                    Label.ENV_CONFIG: schema.str,
                    Label.TEMPLATE_SERVICE_NAME: schema.str(service_name),
                    Label.SERVICE_NAME: schema.str(f'{service_name}-{self.env_id}'),
                }),
                **extra,
            })

        assert dc_cfg == schema.dict({
            'version': schema.str('3'),
            'services': schema.dict({
                f'cache-{self.env_id}': service_schema(
                    'cache',
                    links=schema.list([
                        schema.str(f'redis-{self.env_id}'),
                        schema.str(f'db-{self.env_id}:database'),
                    ]),
                ),
                f'redis-{self.env_id}': service_schema('redis'),
                f'db-{self.env_id}': service_schema('db'),
            }),
            'networks': schema.dict({}),
        })
