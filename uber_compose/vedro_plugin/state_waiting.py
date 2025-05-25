from functools import partial
from typing import Awaitable
from typing import Callable
from typing import List

from rich.text import Text
from rtry import retry

from uber_compose.core.docker_compose_shell.types import ComposeHealth
from uber_compose.core.docker_compose_shell.types import ComposeState
from uber_compose.core.docker_compose_shell.types import ServiceComposeState
from uber_compose.core.docker_compose_shell.types import ServicesComposeState
from uber_compose.helpers.countdown_counter import CountdownCounterKeeper
from uber_compose.helpers.jobs_result import JobResult
from uber_compose.helpers.state_keeper import ServicesState
from uber_compose.helpers.state_keeper import StateKeeper
from uber_compose.output.console import CONSOLE
from uber_compose.output.styles import Style
from uber_compose.vedro_plugin.logger import Logger
from uber_compose.vedro_plugin.logger import WaitVerbosity


def is_service_not_running_or_not_healthy(service_state: ServiceComposeState) -> bool:
    return (service_state.state != ComposeState.RUNNING
            or service_state.health not in (ComposeHealth.EMPTY, ComposeHealth.HEALTHY)
            or (service_state.state == ComposeState.EXITED and service_state.exit_code != 0))


async def check_all_services_up(
    get_services_state: Callable[[], Awaitable[ServicesComposeState]],
    services: List[str],
    counter_keeper: CountdownCounterKeeper,
    state_keeper: StateKeeper,
    verbose: WaitVerbosity = WaitVerbosity.FULL,
) -> JobResult:
    output_style = Style()
    logger = Logger(CONSOLE)

    if state_keeper.in_state(ServicesState.FIRST_STATE):
        logger.log(Text('Starting services check up', style=output_style.info))
        state_keeper.update_state(ServicesState.DEFAULT_STATE)

    services_state = await get_services_state()

    is_all_up = (all([
        service.state == ComposeState.RUNNING or (service.state == ComposeState.EXITED and service.exit_code == 0)
        for service in services_state if service.name in services
    ]) and all([
        service.health in (ComposeHealth.EMPTY, ComposeHealth.HEALTHY)
        for service in services_state if service.name in services
    ]))

    if is_all_up:
        if verbose == WaitVerbosity.COMPACT:
            logger.log(Text(f' ✔ All services up\n', style=output_style.mark_neutral))
            logger.flush()
        if verbose == WaitVerbosity.FULL:
            logger.log(Text(f' ✔ All services up:', style=output_style.mark_neutral))
            logger.log(services_state.as_rich_text(style=output_style))
            logger.flush()
        return JobResult.GOOD

    counter_keeper.tick()
    if counter_keeper.is_done():
        logger.log(Text(' ✗ Stop retries. Still not ready services:', style=output_style.bad))
        logger.log(services_state.as_rich_text(style=output_style))
        logger.flush()
        return JobResult.BAD

    if state_keeper.not_in_state(services_state):
        logger.log(Text(f' ✗ Still not ready services:', style=output_style.bad))
        logger.log(services_state.as_rich_text(
            filter=is_service_not_running_or_not_healthy,
            style=output_style
        ))
        logger.flush()
        state_keeper.update_state(services_state)

    return JobResult.BAD


class WaitAllServicesUp:
    def __init__(self, attempts: int = 100, delay_s: int = 3):
        self._attempts = attempts
        self._delay_s = delay_s

    def make_checker(self) -> Callable:
        return partial(
            retry(
                attempts=self._attempts,
                delay=self._delay_s,
                until=lambda x: x != JobResult.GOOD
            )(check_all_services_up),
            counter_keeper=CountdownCounterKeeper(self._attempts),
            state_keeper=StateKeeper(),
        )


wait_all_services_up = WaitAllServicesUp
