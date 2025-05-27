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
    is_fault_exit = (service_state.state != ComposeState.RUNNING
                     and (service_state.state == ComposeState.EXITED and service_state.exit_code != 0))
    is_not_healthy = (service_state.state == ComposeState.RUNNING
                      and service_state.health not in (ComposeHealth.EMPTY, ComposeHealth.HEALTHY))

    return is_fault_exit or is_not_healthy


async def wait_all_services_up(attempts, delay_s, logger_func: Callable, get_compose_state,
                               is_service_in_bad_state=is_service_not_running_or_not_healthy) -> JobResult:
    counter_keeper = CountdownCounterKeeper(attempts)
    state_keeper = StateKeeper()

    async def check_once() -> JobResult:
        output_style = Style()

        if state_keeper.in_state(ServicesState.FIRST_STATE):
            logger_func(Text('Starting services check up', style=output_style.info))
            state_keeper.update_state(ServicesState.DEFAULT_STATE)

        services_state = await get_compose_state()
        non_ready_services = [
            service
            for service in services_state
            if is_service_in_bad_state(service)
        ]

        if not non_ready_services:
            logger_func(Text(f' ✔ All services up\n', style=output_style.mark_neutral))
            return JobResult.GOOD

        # some service not ready routine
        counter_keeper.tick()

        if counter_keeper.is_done():
            logger_func(Text(' ✗ Stop retries. Still not ready services:', style=output_style.bad))
            logger_func(services_state.as_rich_text(style=output_style))
            return JobResult.BAD

        if state_keeper.not_in_state(services_state):
            logger_func(Text(f' ✗ Still not ready services:', style=output_style.bad))
            logger_func(services_state.as_rich_text(
                filter=is_service_in_bad_state,
                style=output_style
            ))
            state_keeper.update_state(services_state)

        return JobResult.BAD

    return await retry(
        attempts=attempts,
        delay=delay_s,
        until=lambda x: x != JobResult.GOOD,
    )(check_once)()
