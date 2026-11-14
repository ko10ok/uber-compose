import os

from docker import APIClient

from uber_compose.helpers.labels import Label

TEST_DOCKER_DAEMON_URL = 'http://test-docker-daemon:2375'


def get_container_by_service(
    service_name: str,
    env_id: str | None = None,
    containers: list[dict] | None = None,
) -> dict:
    containers = _containers_or_all(containers)

    matching_containers = [
        container
        for container in containers
        if _matches_service(container, service_name)
        and (env_id is None or container.get('Labels', {}).get(Label.ENV_ID) == env_id)
    ]

    assert len(matching_containers) == 1, (
        f'Expected exactly one container for service "{service_name}"'
        f'{f" in env {env_id}" if env_id else ""}, found {len(matching_containers)}'
    )
    return matching_containers[0]


def get_containers_by_env_id(env_id: str, containers: list[dict] | None = None) -> list[dict]:
    return [
        container
        for container in _containers_or_all(containers)
        if container.get('Labels', {}).get(Label.ENV_ID) == env_id
    ]


def get_env_snapshot(env_id: str, containers: list[dict] | None = None) -> dict[str, dict]:
    return {
        container['Id']: {
            'State': container['State'],
            'Service': container.get('Labels', {}).get('com.docker.compose.service'),
        }
        for container in get_containers_by_env_id(env_id, containers)
    }


def _containers_or_all(containers: list[dict] | None = None) -> list[dict]:
    if containers is not None:
        return containers

    client = APIClient(base_url=TEST_DOCKER_DAEMON_URL)
    project_name = os.environ.get('COMPOSE_PROJECT_NAME')
    return [
        container
        for container in client.containers(all=True)
        if container.get('Labels', {}).get('com.docker.compose.project') == project_name
    ]


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
