import os

from docker import APIClient

from uber_compose.helpers.labels import Label

TEST_DOCKER_DAEMON_URL = 'http://test-docker-daemon:2375'


def get_container_by_service(service_name: str, env_id: str | None = None) -> dict:
    client = APIClient(base_url=TEST_DOCKER_DAEMON_URL)
    containers = client.containers(all=True)

    project_name = os.environ.get('COMPOSE_PROJECT_NAME')
    matching_containers = [
        container
        for container in containers
        if container.get('Labels', {}).get('com.docker.compose.project') == project_name
        and _matches_service(container, service_name)
        and (env_id is None or container.get('Labels', {}).get(Label.ENV_ID) == env_id)
    ]

    assert len(matching_containers) == 1, (
        f'Expected exactly one container for service "{service_name}"'
        f'{f" in env {env_id}" if env_id else ""}, found {len(matching_containers)}'
    )
    return matching_containers[0]


def _matches_service(container: dict, service_name: str) -> bool:
    labels = container.get('Labels', {})

    template_service_name = labels.get(Label.TEMPLATE_SERVICE_NAME)
    if template_service_name is not None:
        return template_service_name == service_name

    compose_service_name = labels.get('com.docker.compose.service', '')
    return (
        compose_service_name == service_name
        or compose_service_name.startswith(f'{service_name}-')
    )
