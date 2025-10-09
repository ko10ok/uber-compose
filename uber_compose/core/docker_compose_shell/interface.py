import asyncio
import os
import pprint
import shlex
import sys
from asyncio import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from typing import Coroutine
from typing import NamedTuple

from rich.text import Text
from rtry import retry

from uber_compose.core.constants import Constants
from uber_compose.core.docker_compose_shell.types import ServicesComposeState
from uber_compose.core.utils.process_command_output import process_output_till_done
from uber_compose.core.utils.shell_process import parse_process_command_name
from uber_compose.helpers.jobs_result import JobResult
from uber_compose.helpers.jobs_result import OperationError
from uber_compose.output.console import CONSOLE
from uber_compose.output.console import Logger
from uber_compose.output.styles import Style

DC_BIN = '/usr/bin/docker'
COMPOSE = f'{DC_BIN} compose'


class NoDockerCompose(BaseException):
    ...


class ExecWasntSuccesfullyDone(BaseException):
    ...


class ProcessExit:
    def __eq__(self, other):
        return isinstance(other, ProcessExit)


class ComposeShellInterface:
    def __init__(self,
                 compose_files: str,
                 in_docker_project_root: Path,
                 logger: Logger,
                 execution_envs: dict = None,
                 cfg_constants: Constants = None
                 ) -> None:
        self.cfg_constants = cfg_constants if cfg_constants else Constants()

        self.logger = logger
        self.compose_files = compose_files
        self.in_docker_project_root = str(in_docker_project_root)
        self.execution_envs = os.environ | {
            'COMPOSE_FILE': self.compose_files,
            'DOCKER_HOST': self.cfg_constants.docker_host,
            'COMPOSE_PROJECT_NAME': self.cfg_constants.compose_project_name,
        }
        if execution_envs is not None:
            self.execution_envs |= execution_envs
        self.extra_exec_params = self.cfg_constants.docker_compose_extra_exec_params

        if self.cfg_constants.cli_compose_util_override:
            logger.system_commands(
                f'Using overridden {self.cfg_constants.cli_compose_util_override} CLI compose command'
            )

            # for check binary existance
            global DC_BIN
            DC_BIN = self.cfg_constants.cli_compose_util_override

            # for binary usage
            global COMPOSE
            COMPOSE = self.cfg_constants.cli_compose_util_override

        # check if DC_BIN exists
        if not Path(DC_BIN).exists():
            raise NoDockerCompose(
                f'Docker Compose binary not found at {DC_BIN}. Please install Docker Client with compose: \n   Alpine - apk add docker-cli docker-cli-compose\n   Debian/Ubuntu - apt install docker-ce-cli docker-compose-plugin')

    @retry(attempts=10, delay=1, until=lambda x: x == JobResult.BAD)
    async def dc_state(self, env: dict = None, root: Path | str = None) -> ServicesComposeState | OperationError:
        sys.stdout.flush()

        if env is None:
            env = {}
        env = self.execution_envs | env

        if root is None:
            root = self.in_docker_project_root

        process = await asyncio.create_subprocess_shell(
            cmd := f"{COMPOSE} --project-directory {root}" + " ps -a --format='{{json .}}'",
            env=env,
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.logger.system_commands(Text(
            f'{cmd}',
            style=Style.context
        ))
        stdout, stderr = await process_output_till_done(process, self.logger.system_commands_debug)

        if process.returncode != 0:
            print(f"Can't get container's status {stdout} {stderr}")
            return OperationError(f'Command: {cmd}\nStdout:\n{stdout}\n\nStderr:\n{stderr}')

        state_result = ServicesComposeState(stdout.decode('utf-8'))
        self.logger.system_commands_output(state_result.as_rich_text())
        return state_result

    @retry(attempts=3, delay=1, until=lambda x: x == JobResult.BAD)
    async def dc_up(self, services: list[str], env: dict = None, root: Path | str = None) -> JobResult | OperationError:
        sys.stdout.flush()

        if env is None:
            env = {}
        env = self.execution_envs | env

        if root is None:
            root = self.in_docker_project_root

        process = await asyncio.create_subprocess_shell(
            cmd := f'{COMPOSE} --project-directory {root} up --timestamps --no-deps --pull missing '
                   '--timeout 300 -d ' + ' '.join(services),
            env=env,
            cwd=root,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        self.logger.commands(Text(
            f'{cmd}',
            style=Style.context
        ))
        self.logger.system_commands_environment_debug(Text(
            f'running in {root}; with {pprint.pformat(env)}',
            style=Style.regular
        ))
        stdout, stderr = await process_output_till_done(process, self.logger.command_output)

        if process.returncode != 0:
            return OperationError(f'Command: {cmd}\nStdout:\n{stdout}\n\nStderr:\n{stderr}')

        return JobResult.GOOD

    @retry(attempts=3, delay=1, until=lambda x: x == JobResult.BAD)
    async def dc_logs(self, services: list[str], env: dict = None, root: Path | str = None, logs_param='--no-log-prefix'
                      ) -> tuple[JobResult, bytes] | tuple[OperationError, None]:
        sys.stdout.flush()

        if env is None:
            env = {}
        env = self.execution_envs | env

        if root is None:
            root = self.in_docker_project_root

        if services is None:
            services = []
        services = ' '.join(services)

        process = await asyncio.create_subprocess_shell(
            cmd := f'{COMPOSE} --project-directory {root} logs {logs_param} {services}',
            env=env,
            cwd=root,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        self.logger.commands(Text(
            f'{cmd}',
            style=Style.context
        ))
        stdout, stderr = await process_output_till_done(process, self.logger.command_output)

        if process.returncode != 0:
            print(f"Can't get {services} logs")
            state_result = await self.dc_state()
            if state_result == JobResult.GOOD:
                return OperationError(
                    f'Command: {cmd}\nStdout:\n{stdout}\n\nStderr:\n{stderr}\n\nComposeState:\n{state_result.as_rich_text()}'
                ), None
            return OperationError(f'Command: {cmd}\nStdout:\n{stdout}\n\nStderr:\n{stderr}\n\nComposeState:\n{state_result}'), None

        return JobResult.GOOD, stdout

    @retry(attempts=3, delay=1, until=lambda x: x == JobResult.BAD)
    async def dc_exec(self, container: str, cmd: str, extra_env: dict = None, env: dict = None, root: Path | str = None,
                      detached=False,
                      ) -> tuple[JobResult, bytes, bytes] | tuple[OperationError, bytes, bytes]:
        self.logger.stage_details(f'Executing {cmd} in {container} container')
        sys.stdout.flush()

        if extra_env is None:
            extra_env = {}
        extra_env_str = ' '.join(
            f'-e {key}={shlex.quote(str(value))}' for key, value in extra_env.items()
        )

        if env is None:
            env = {}
        env = self.execution_envs | env

        if root is None:
            root = self.in_docker_project_root

        detached_param_str = '-d' if detached else ''
        detached_end_str = ' &' if detached else ''
        detached_end_str = ''

        process = await asyncio.create_subprocess_shell(
            cmd := f'{COMPOSE} --project-directory {root} exec {extra_env_str} {detached_param_str} {self.extra_exec_params} {container} {cmd} {detached_end_str}',
            env=env,
            cwd=root,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        self.logger.commands(Text(
            f'{cmd}' + (f'\n  with params: {extra_env_str}' if extra_env else ''),
            style=Style.context
        ))
        self.logger.system_commands_environment_debug(Text(
            f'running in {root}; with {pprint.pformat(env)}',
            style=Style.regular
        ))
        stdout, stderr = await process_output_till_done(process, self.logger.command_output)

        if process.returncode != 0:
            state_result = await self.dc_state()
            if state_result == JobResult.GOOD:
                return OperationError(
                    f'Command: {cmd}\nStdout:\n{stdout}\n\nStderr:\n{stderr}\n\nComposeState:\n{state_result.as_rich_text()}'
                ), stdout, stderr
            return OperationError(
                f'Command: {cmd}\nStdout:\n{stdout}\n\nStderr:\n{stderr}\n\nComposeState:\n{state_result}'
            ), stdout, stderr

        return JobResult.GOOD, stdout, stderr

    async def _dc_exec_process_pids(self, container: str,
                                    cmd: str,
                                    env: dict = None,
                                    root: Path | str = None,
                                    ) -> tuple[JobResult, bytes, bytes] | list[int] | tuple[OperationError, bytes, bytes]:
        if env is None:
            env = {}
        env = self.execution_envs | env

        if root is None:
            root = self.in_docker_project_root

        cmd = parse_process_command_name(cmd)
        process_state = await asyncio.create_subprocess_shell(
            check_cmd := f'{COMPOSE} --project-directory {root} exec {self.extra_exec_params} {container} pidof {cmd}',
            env=env,
            cwd=root,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        self.logger.system_commands(
            Text(f'{check_cmd}', style=Style.context)
        )
        stdout, stderr = await process_state.communicate()
        check_output = stdout.decode('utf-8')
        sys_error = stderr.decode("utf-8")

        self.logger.system_commands_debug(f'Pids of command {cmd} in {container}:\n {check_output} \nErr: {sys_error}')

        if check_output != '':
            try:
                pids = [int(pid) for pid in check_output.split(' ')]
                self.logger.stage_details(f'Process still running: {cmd} in {container} with:\n  {pids}')
                await self._dc_exec_print_processes(container, env, root)
                return pids
            except ValueError:
                ...
            if self.cfg_constants.ignore_pidof_unexistance:
                self.logger.stage_details(f'Error parsing pids from {check_output} for {cmd} in {container}')
                return [-1]
            self.logger.error(f'Somthing wrong for {cmd} in {container}:\n  {check_output}')
            return [-1]
        else:
            self.logger.stage_info(f'Process done: {cmd} in {container}')
            return []

    async def _dc_exec_print_processes(self, container: str,
                                       env: dict = None,
                                       root: Path | str = None,
                                       ) -> None:
        if env is None:
            env = {}
        env = self.execution_envs | env

        if root is None:
            root = self.in_docker_project_root

        processes_state = await asyncio.create_subprocess_shell(
            get_cmd := f'{COMPOSE} --project-directory {root} exec {self.extra_exec_params} {container} top -n 1',
            env=env,
            cwd=root,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await processes_state.communicate()
        self.logger.stage_debug(f'Processes state in {container}')
        self.logger.stage_debug(stdout.decode('utf-8'))
        self.logger.stage_debug(stderr.decode('utf-8'))

    class ExecResult(NamedTuple):
        check_result: bool
        err: OperationError | None = None
        stdout: str = ''
        stderr: str = ''

    async def dc_exec_until_state(self, container: str,
                                  cmd: str,
                                  extra_env: dict[str, str] = None,
                                  wait: Callable | ProcessExit | None = ProcessExit(),
                                  break_on_timeout: bool = True,
                                  kill_before: bool = True,
                                  kill_after: bool = True,
                                  env: dict = None,
                                  root: Path | str = None,
                                  ) -> ExecResult:
        cmd = cmd.strip()
        cmd_name = parse_process_command_name(cmd)

        if kill_before:
            await self.dc_exec(container, f'killall {cmd_name}')

        check_done_result = True
        if cmd.endswith('&'):
            self.logger.stage_details(f'Command {cmd} is detached-mode running, skipping any finish checks')
            cmd = cmd[:-1]
            wait = None

        result, stdout, stderr = await self.dc_exec(container, cmd, extra_env=extra_env, env=env, root=root,
                                                    detached=(wait != ProcessExit()))

        if isinstance(result, OperationError):
            check_done_result = False

        if wait == ProcessExit():
            self.logger.stage_info(Text('Retrieving process IDs wait completion', style=Style.info))
            process_ids = await retry(
                attempts=Constants().exec_pids_check_attempts_count,
                delay=Constants().exec_pids_check_retry_delay,
                until=lambda pids: pids != [] and pids != [-1]
            )(self._dc_exec_process_pids)(container, cmd)
            self.logger.stage_debug(f'pids retrieved {process_ids}')
            if process_ids:
                if process_ids == [-1]:
                    self.logger.stage_details(
                        f'Process:\n{cmd}\nwas not checked for completion due to no "pidof" tool in container'
                    )
                else:
                    self.logger.error(Text('Process was not completed', style=Style.suspicious))
                    check_done_result = False
                    if break_on_timeout:
                        raise ExecWasntSuccesfullyDone(
                            f'\nProcess\n{cmd}\nwas not finished in {Constants().exec_pids_check_attempts_count}x'
                            f'{Constants().exec_pids_check_retry_delay} seconds'
                        )
        elif isinstance(wait, Callable):
            if asyncio.iscoroutinefunction(wait):
                check_done_result = await wait(container, cmd, env, extra_env, break_on_timeout)
            else:
                check_done_result = wait(container, cmd, env, extra_env, break_on_timeout)

        if kill_after:
            await self.dc_exec(container, f'killall {cmd_name}')

        return ComposeShellInterface.ExecResult(check_done_result, err=result, stdout=stdout, stderr=stderr)

    @retry(attempts=3, delay=1, until=lambda x: x == JobResult.BAD)
    async def dc_down(self, services: list[str], env: dict = None,
                      root: Path | str = None) -> JobResult | OperationError:
        self.logger.stage_info(f'Downing {services} containers')
        sys.stdout.flush()

        if env is None:
            env = {}
        env = self.execution_envs | env

        if root is None:
            root = self.in_docker_project_root

        process = await asyncio.create_subprocess_shell(
            cmd := f'{COMPOSE} --project-directory {root} down ' + ' '.join(services),
            env=env,
            cwd=root,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        self.logger.commands(Text(
            f'{cmd}',
            style=Style.context
        ))
        self.logger.system_commands_environment_debug(Text(
            f'running in {root}; with {pprint.pformat(env)}',
            style=Style.regular
        ))
        stdout, stderr = await process_output_till_done(process, self.logger.command_output)

        if process.returncode != 0:
            # TODO swap print to CONSOLE
            print(f"Can't down {services} successfully")
            state_result = await self.dc_state()
            if state_result == JobResult.GOOD:
                return OperationError(
                    f'Command: {cmd}\nStdout:\n{stdout}\n\nStderr:\n{stderr}\n\nComposeState:\n{state_result.as_rich_text()}'
                )
            return OperationError(f'Command: {cmd}\nStdout:\n{stdout}\n\nStderr:\n{stderr}\n\nComposeState:\n{state_result}')

        return JobResult.GOOD
