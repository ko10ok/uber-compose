from typing import Callable

from rich.text import Text
from rtry import retry

from uber_compose.core.docker_compose_shell.types import ComposeHealth
from uber_compose.core.docker_compose_shell.types import ComposeState
from uber_compose.core.docker_compose_shell.types import ServiceComposeState
from uber_compose.helpers.countdown_counter import CountdownCounterKeeper
from uber_compose.helpers.jobs_result import JobResult
from uber_compose.helpers.state_keeper import ServicesState
from uber_compose.helpers.state_keeper import StateKeeper
from uber_compose.output.styles import Style


def is_service_not_running_or_not_healthy(service_state: ServiceComposeState) -> bool:
    if service_state.state == ComposeState.RUNNING:
        return service_state.health not in (ComposeHealth.EMPTY, ComposeHealth.HEALTHY)

    if service_state.state == ComposeState.EXITED:
        return service_state.exit_code != 0

    return True


def is_service_exited_unexpectedly(service_state: ServiceComposeState) -> bool:
    return (
        service_state.state == ComposeState.EXITED
        and service_state.exit_code != 0
    )


def is_service_unhealthy(service_state: ServiceComposeState) -> bool:
    return (
        service_state.state == ComposeState.RUNNING
        and service_state.health == ComposeHealth.UNHEALTHY
    )


def is_service_failed_without_restart_policy(
    service_state: ServiceComposeState,
    has_restart_policy: Callable[[ServiceComposeState], bool],
) -> bool:
    if has_restart_policy(service_state):
        return False

    return (
        is_service_exited_unexpectedly(service_state)
        or is_service_unhealthy(service_state)
    )


async def wait_all_services_up(attempts, delay_s, logger_func: Callable, get_compose_state,
                               is_service_in_bad_state=is_service_not_running_or_not_healthy,
                               service_filter: Callable = None,
                               has_restart_policy: Callable[[ServiceComposeState], bool] = None,
                               ) -> JobResult:
    counter_keeper = CountdownCounterKeeper(attempts)
    state_keeper = StateKeeper()

    if service_filter is None:
        service_filter = lambda service_state: True

    if has_restart_policy is None:
        has_restart_policy = lambda service_state: False

    def is_service_failed_without_restart(service_state: ServiceComposeState) -> bool:
        return is_service_failed_without_restart_policy(service_state, has_restart_policy)

    async def check_once() -> JobResult | None:
        output_style = Style()

        if state_keeper.in_state(ServicesState.FIRST_STATE):
            logger_func(Text('Starting services check up', style=output_style.info))
            state_keeper.update_state(ServicesState.DEFAULT_STATE)

        services_state = (await get_compose_state()).get_all_for(service_filter)
        non_ready_services = [
            service
            for service in services_state
            if is_service_in_bad_state(service)
        ]

        if not non_ready_services:
            logger_func(Text(' ✔ All services up\n', style=output_style.mark_neutral))
            return JobResult.GOOD

        if any(is_service_failed_without_restart(service) for service in services_state):
            logger_func(Text(' ✗ Service failed without restart policy. Stop waiting:', style=output_style.bad))
            logger_func(services_state.as_rich_text(
                filter=is_service_failed_without_restart,
                style=output_style
            ))
            return None

        # some service not ready routine
        counter_keeper.tick()

        if counter_keeper.is_done():
            logger_func(Text(' ✗ Stop retries. Still not ready services:', style=output_style.bad))
            logger_func(services_state.as_rich_text(style=output_style))
            return JobResult.BAD

        if state_keeper.not_in_state(services_state):
            logger_func(Text(' ✗ Still not ready services:', style=output_style.bad))
            logger_func(services_state.as_rich_text(
                filter=is_service_in_bad_state,
                style=output_style
            ))
            state_keeper.update_state(services_state)

        return JobResult.BAD

    result = await retry(
        attempts=attempts,
        delay=delay_s,
        until=lambda x: x == JobResult.BAD,
    )(check_once)()
    return result if result == JobResult.GOOD else JobResult.BAD
