from uber_compose import Environment
from uber_compose.core.docker_compose_shell.types import ServicesComposeState
from uber_compose.core.utils.compose_instance_cfg import get_service_map
from uber_compose.core.utils.state_waiting import is_service_not_running_or_not_healthy
from uber_compose.helpers.labels import Label


def calc_broken_services(
    services_state: ServicesComposeState,
    config_template: Environment,
    excluded_from_check: list[str] = None,
    env_id: str = None,
) -> list[str]:
    if excluded_from_check is None:
        excluded_from_check = []

    if env_id is None and services_state.get_any() is not None:
        env_id = services_state.get_any().labels.get(Label.ENV_ID)

    if env_id is not None:
        expected_services_map = get_service_map(config_template, env_id)
    else:
        expected_services_map = {
            service_name: service_name
            for service_name in config_template.get_services_names()
        }

    non_ready_services = [
        service.name
        for service in services_state
        if is_service_not_running_or_not_healthy(service)
    ]
    not_included_services = [
        service
        for service in expected_services_map.values()
        if service not in services_state.get_services_names()
    ]
    skipped_overridden_services = [
        expected_services_map.get(service.service.name, service.service.name)
        for service in config_template.get_overridden_services()
        if expected_services_map.get(service.service.name, service.service.name)
        not in services_state.get_services_names()
    ]
    return list(
        set(non_ready_services) | set(not_included_services)
        - set(excluded_from_check) - set(skipped_overridden_services)
    )
