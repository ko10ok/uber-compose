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
    return d.containers(all=True)


def retrieve_dockerish_containers() -> list[Container]:
    d = APIClient(
        base_url="http://test-docker-daemon:2375",
    )
    d = docker.from_env()
    res = d.containers.list(all=True)
    return res


def no_docker_containers():
    d = APIClient(
        base_url="http://test-docker-daemon:2375",
    )
    for container in retrieve_all_docker_containers():
        d.stop(container['Id'])
        d.remove_container(container['Id'])

    for network in d.networks():
        if network.get('Name') in BUILTIN_NETWORKS:
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
