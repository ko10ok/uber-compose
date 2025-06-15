from uber_compose.env_description.env_types import Environment
from uber_compose.env_description.env_types import Service
from uber_compose.utils.docker_compose_files_path import get_absolute_compose_files
from uber_compose.utils.docker_compose_service_deps import parse_docker_compose_services_deps


def make_services_for(compose_files: str) -> list[Service]:
    return [Service(name) for name in parse_docker_compose_services_deps(compose_files)]


def make_default_environment(compose_files: str, desc='AUTO_SCANNED') -> Environment:
    return Environment(
        *make_services_for(compose_files),
        description=desc,
    )
