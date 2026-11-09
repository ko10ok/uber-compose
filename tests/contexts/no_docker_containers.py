import os

import docker
from docker import APIClient
from docker.errors import APIError
from docker.models.containers import Container

from uber_compose.helpers.labels import Label

BUILTIN_NETWORKS = {'bridge', 'host', 'none'}


def retrieve_all_docker_containers() -> list[dict]:
    d = APIClient(
        base_url="http://test-docker-daemon:2375",
    )
    project_name = os.environ.get('COMPOSE_PROJECT_NAME')
    return [
        container
        for container in d.containers(all=True)
        if container.get('Labels', {}).get('com.docker.compose.project') == project_name
    ]


def retrieve_dockerish_containers() -> list[Container]:
    d = docker.from_env()
    project_name = os.environ.get('COMPOSE_PROJECT_NAME')
    return d.containers.list(
        all=True,
        filters={'label': f'com.docker.compose.project={project_name}'},
        ignore_removed=True,
    )


def no_docker_containers():
    d = APIClient(
        base_url="http://test-docker-daemon:2375",
    )
    for container in retrieve_all_docker_containers():
        d.stop(container['Id'])
        d.remove_container(container['Id'])

    project_name = os.environ.get('COMPOSE_PROJECT_NAME')
    for network in d.networks():
        name = network.get('Name', '')
        if name in BUILTIN_NETWORKS:
            continue
        if not project_name or not name.startswith(f'{project_name}_'):
            continue
        try:
            d.remove_network(network['Id'])
        except APIError:
            pass


def stopped_docker_container(name):
    d = APIClient(
        base_url="http://test-docker-daemon:2375",
    )
    for container in retrieve_all_docker_containers():
        if container.get('Labels', {}).get(Label.SERVICE_NAME) == name:
            d.stop(container['Id'])
            d.remove_container(container['Id'])


def created_docker_container(name):
    d = APIClient(
        base_url="http://test-docker-daemon:2375",
    )
    for container in retrieve_all_docker_containers():
        if container.get('Labels', {}).get(Label.SERVICE_NAME) != name:
            continue

        d.stop(container['Id'])
        d.remove_container(container['Id'])
        d.create_container(
            image=container['Image'],
            command=container['Command'],
            name=container['Names'][0].lstrip('/'),
            labels=container['Labels'],
        )
        return

    raise AssertionError(f'Container with service name "{name}" not found')


def paused_docker_container(name):
    d = APIClient(
        base_url="http://test-docker-daemon:2375",
    )
    for container in retrieve_all_docker_containers():
        if container.get('Labels', {}).get(Label.SERVICE_NAME) != name:
            continue

        d.pause(container['Id'])
        return

    raise AssertionError(f'Container with service name "{name}" not found')
