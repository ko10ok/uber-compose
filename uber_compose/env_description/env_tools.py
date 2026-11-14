from warnings import warn

from uber_compose.env_description.env_types import Service
from uber_compose.env_description.env_types import ServiceMode


def singleton(service: Service) -> Service:
    return Service(
        name=service.name,
        env=service.env,
        events_handlers=service.events_handlers,
        mode=ServiceMode.SINGLETON,
        mounted_files=service.mounted_files,
    )


def off(service: Service) -> Service:
    warn('will be deprecated')
    return Service(
        name=service.name,
        env=service.env,
        events_handlers=service.events_handlers,
        mode=ServiceMode.OFF,
        mounted_files=service.mounted_files,
    )
