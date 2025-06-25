from uber_compose import Environment
from uber_compose.core.docker_compose_shell.types import ServicesComposeState
from uber_compose.core.utils.state_waiting import is_service_not_running_or_not_healthy


def calc_broken_services(
    services_state: ServicesComposeState, config_template: Environment, excluded_from_check: list[str] = None
) -> list[str]:
    if excluded_from_check is None:
        excluded_from_check = []
    non_ready_services = [
        service.name
        for service in services_state
        if is_service_not_running_or_not_healthy(service)
    ]
    not_included_services = [
        service
        for service in config_template.get_services_names()
        if service not in services_state.get_services_names()
    ]
    skipped_overridden_services = [
        service.service.name
        for service in config_template.get_overridden_services()
        if service.service.name not in services_state.get_services_names()
    ]
    return list(
        set(non_ready_services) | set(not_included_services) - set(excluded_from_check) - set(skipped_overridden_services)
    )
