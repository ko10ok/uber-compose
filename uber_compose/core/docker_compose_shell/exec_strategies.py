import asyncio
from dataclasses import dataclass
from pathlib import Path
import shlex
from time import perf_counter
from typing import Callable
from typing import TYPE_CHECKING
from typing import Type
from uuid import uuid4

from uber_compose.core.constants import Constants
from uber_compose.core.docker_compose_shell.interface import ExecWasntSuccesfullyDone
from uber_compose.core.docker_compose_shell.interface import ProcessExit
from uber_compose.core.docker_compose_shell.interface import TimeOutCheck
from uber_compose.core.docker_compose_shell.types import ExecLifeCyclePolicy
from uber_compose.core.utils.shell_process import parse_process_command_name
from uber_compose.helpers.exec_result import ExecResult
from uber_compose.helpers.exec_result import ExecTimeout
from uber_compose.helpers.jobs_result import JobResult

if TYPE_CHECKING:
    from uber_compose.core.docker_compose_shell.interface import ComposeShellInterface


INITIAL_POLL_DELAY_S = 0.05
MAX_POLL_DELAY_S = 1.0


@dataclass(frozen=True)
class ExecContext:
    shell: "ComposeShellInterface"
    container: str
    command: str
    extra_env: dict[str, str] | None
    wait: Callable | ProcessExit | None
    timeout: TimeOutCheck | None
    life_cycle_policy: ExecLifeCyclePolicy
    env: dict | None = None
    root: Path | str | None = None


class ExecStrategy:
    async def execute(self, context: ExecContext) -> ExecResult | ExecTimeout:
        raise NotImplementedError


class PidofExecStrategy(ExecStrategy):
    """Legacy exec strategy. Keeps the original pidof-based wait logic untouched."""

    async def execute(self, context: ExecContext) -> ExecResult | ExecTimeout:
        shell = context.shell
        log_file = f'{uuid4()}.log'
        cmd = f'sh -c \'{shlex.quote(context.command)[1:-1]} > /tmp/{log_file} 2>&1\''

        result = await shell.dc_exec_until_state(
            container=context.container,
            cmd=cmd,
            extra_env=context.extra_env,
            wait=context.wait,
            timeout=context.timeout,
            break_on_timeout=context.life_cycle_policy.break_on_timeout,
            kill_before=context.life_cycle_policy.kill_before_same_old_command_running,
            kill_after=context.life_cycle_policy.kill_after_command_still_running,
            env=context.env,
            root=context.root,
        )

        job_result, stdout, stderr = await shell.dc_exec(
            context.container, f'cat /tmp/{log_file}', env=context.env, root=context.root,
        )
        if job_result != JobResult.GOOD:
            shell.logger.error(
                f'Error executing command in container {context.container}: {stderr}'
            )

        if not result.finished:
            return ExecTimeout(stdout=stdout, cmd=context.command)
        return ExecResult(stdout=stdout, cmd=context.command, exit_code=None)


class StatusFileExecStrategy(ExecStrategy):
    """Async exec strategy which waits for a status file and returns the command exit code."""

    async def execute(self, context: ExecContext) -> ExecResult | ExecTimeout:
        shell = context.shell
        command = context.command.strip()
        wait = context.wait
        timeout = self._resolve_timeout(context.timeout)

        if command.endswith('&'):
            command = command[:-1].strip()
            wait = None

        cmd_name = parse_process_command_name(command) if command else ''

        if context.life_cycle_policy.kill_before_same_old_command_running:
            await self._kill(shell, context, cmd_name)

        uid = uuid4().hex
        log_file = f'/tmp/uber-compose-exec-{uid}.log'
        exit_file = f'/tmp/uber-compose-exec-{uid}.exit'
        marker = f'__UBER_COMPOSE_EXIT_{uid}__'

        wrapped_command = (
            f'( {command} ) > {log_file} 2>&1; '
            f'printf \'%s\' "$?" > {exit_file}'
        )
        launch_cmd = f'sh -c {shlex.quote(wrapped_command)}'
        launch_result = await shell.dc_exec_raw(
            context.container,
            launch_cmd,
            extra_env=context.extra_env,
            env=context.env,
            root=context.root,
            detached=True,
        )
        if launch_result.returncode != 0:
            raise ExecWasntSuccesfullyDone(
                f'\nCommand\n{command}\nwas not started in {context.container}:\n'
                f'{launch_result.stdout=}\n{launch_result.stderr=}'
            )

        if wait is None:
            if context.life_cycle_policy.kill_after_command_still_running:
                await self._kill(shell, context, cmd_name)
            stdout, _ = await self._read_result(
                shell, context, log_file, exit_file, marker,
            )
            return ExecResult(stdout=stdout, cmd=command, exit_code=None)

        if wait == ProcessExit():
            finished = await self._wait_for_exit_file(
                shell, context, exit_file, timeout,
            )
            stdout, exit_code = await self._read_result(
                shell, context, log_file, exit_file, marker,
            )
            if not finished:
                if context.life_cycle_policy.kill_after_command_still_running:
                    await self._kill(shell, context, cmd_name)
                return ExecTimeout(stdout=stdout, cmd=command)
            return ExecResult(stdout=stdout, cmd=command, exit_code=exit_code)

        finished = await self._run_wait_callable(context, command, wait)
        stdout, exit_code = await self._read_result(
            shell, context, log_file, exit_file, marker,
        )
        if not finished:
            if context.life_cycle_policy.kill_after_command_still_running:
                await self._kill(shell, context, cmd_name)
            return ExecTimeout(stdout=stdout, cmd=command)
        return ExecResult(stdout=stdout, cmd=command, exit_code=exit_code)

    @staticmethod
    def _resolve_timeout(timeout: TimeOutCheck | None) -> TimeOutCheck:
        if timeout is not None:
            return timeout
        return TimeOutCheck(
            attempts=Constants().exec_pids_check_attempts_count,
            delay_s=Constants().exec_pids_check_retry_delay,
        )

    async def _wait_for_exit_file(self, shell: "ComposeShellInterface", context: ExecContext,
                                  exit_file: str, timeout: TimeOutCheck) -> bool:
        timeout_s = max(timeout.attempts * timeout.delay_s, timeout.delay_s, INITIAL_POLL_DELAY_S)
        started_at = perf_counter()
        delay_s = INITIAL_POLL_DELAY_S

        while True:
            if await self._exit_file_exists(shell, context, exit_file):
                return True

            remaining_s = timeout_s - (perf_counter() - started_at)
            if remaining_s <= 0:
                return False

            await asyncio.sleep(min(delay_s, remaining_s))
            delay_s = min(delay_s * 2, MAX_POLL_DELAY_S)

    @staticmethod
    async def _exit_file_exists(shell: "ComposeShellInterface", context: ExecContext,
                                exit_file: str) -> bool:
        result = await shell.dc_exec_raw(
            context.container,
            f'test -f {shlex.quote(exit_file)}',
            env=context.env,
            root=context.root,
        )
        return result.returncode == 0

    @staticmethod
    async def _read_result(shell: "ComposeShellInterface", context: ExecContext, log_file: str,
                           exit_file: str, marker: str) -> tuple[bytes, int | None]:
        read_script = (
            f'cat {log_file}; '
            f'printf "\\n{marker}%s" "$(cat {exit_file} 2>/dev/null)"'
        )
        read_result = await shell.dc_exec_raw(
            context.container,
            f'sh -c {shlex.quote(read_script)}',
            env=context.env,
            root=context.root,
        )
        stdout, separator, raw_exit_code = read_result.stdout.partition(
            f'\n{marker}'.encode(),
        )
        if not separator:
            return read_result.stdout, None
        try:
            exit_code = int(raw_exit_code.strip())
        except ValueError:
            exit_code = None
        return stdout, exit_code

    @staticmethod
    async def _run_wait_callable(context: ExecContext, command: str, wait: Callable) -> bool:
        if asyncio.iscoroutinefunction(wait):
            return await wait(
                context.container,
                command,
                context.env,
                context.extra_env,
                context.life_cycle_policy.break_on_timeout,
            )
        return wait(
            context.container,
            command,
            context.env,
            context.extra_env,
            context.life_cycle_policy.break_on_timeout,
        )

    @staticmethod
    async def _kill(shell: "ComposeShellInterface", context: ExecContext, cmd_name: str) -> None:
        if not cmd_name:
            return
        await shell.dc_exec_raw(
            context.container,
            f'killall {shlex.quote(cmd_name)}',
            env=context.env,
            root=context.root,
        )


ExecStrategyType = Type[ExecStrategy]
