from contexts.compose_file import compose_file
from contexts.no_docker_compose_files import no_docker_compose_files
from contexts.no_docker_containers import no_docker_containers
from contexts.no_docker_containers import retrieve_all_docker_containers
from contexts.services_started import services_started
import vedro

from uber_compose import Environment
from uber_compose import Service


@vedro.skip(reason=(
    'Behavior undefined: switching the same env template from parallelism_limit>1 '
    '(service-<env_id> names) to parallelism_limit=1 (unsuffixed service names, default '
    'namespace) between consecutive up() calls. At limit=1, every running non-protected '
    'service gets downed regardless of its template/env_id - should that collapse all '
    'limit>1 namespaced instances, and should the limit=1 instance reuse one of them or '
    'always start fresh? TODO: decide and un-skip.'
))
class Scenario(vedro.Scenario):
    async def given_no_docker_containers(self):
        no_docker_containers()

    async def given_no_docker_compose_files(self):
        no_docker_compose_files()

    async def given_compose_files(self):
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

    async def given_env_template(self):
        self.environment = Environment(Service('s1'), description='env-a')

    async def given_env_already_up_with_parallelism_limit_greater_than_1(self):
        self.first_response = await services_started(
            compose_files=self.compose_files,
            config_template=self.environment,
            parallelism_limit=2,
        )

    async def when_user_up_same_env_with_parallelism_limit_1(self):
        self.second_response = await services_started(
            compose_files=self.compose_files,
            config_template=self.environment,
            parallelism_limit=1,
        )

    async def then_todo_define_expected_behavior(self):
        self.containers = retrieve_all_docker_containers()
        assert False, 'TODO: define expected behavior for limit>1 -> limit=1 transition'
