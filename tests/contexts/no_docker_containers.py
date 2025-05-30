from docker import APIClient
from docker.models.containers import Container
from uber_compose.helpers.labels import Label


def retrieve_all_docker_containers() -> list[Container]:
    d = APIClient(
        base_url="http://test-docker-daemon:2375",
    )
    return d.containers(all=True)


def no_docker_containers():
    d = APIClient(
        base_url="http://test-docker-daemon:2375",
    )
    for container in retrieve_all_docker_containers():
        d.stop(container['Id'])
        d.remove_container(container['Id'])


def stopped_docker_container(name):
    d = APIClient(
        base_url="http://test-docker-daemon:2375",
    )
    for container in retrieve_all_docker_containers():
        if container.get('Labels', {}).get(Label.SERVICE_NAME) == name:
            d.stop(container['Id'])
            d.remove_container(container['Id'])
