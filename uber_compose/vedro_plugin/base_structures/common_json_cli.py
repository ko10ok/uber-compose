import json
import re
from dataclasses import dataclass
from typing import Callable
from typing import Generic
from typing import List
from typing import Optional
from typing import Type
from typing import TypeVar
from warnings import warn

from uber_compose.core.docker_compose_shell.interface import ProcessExit
from uber_compose.uber_compose import TheUberCompose


@dataclass
class CommandResult:
    stdout: list
    stderr: list
    cmd: str
    env: dict[str, str]

    def has_no_errors(self) -> bool:
        return self.stderr == []

class LogLevels:
    TRACE = 'trace'
    DEBUG = 'debug'
    INFO = 'info'
    WARNING = 'warning'
    ERROR = 'error'
    FATAL = 'fatal'
    PANIC = 'panic'


StdOutErrType = list[str | dict]
OutputType = tuple[StdOutErrType, StdOutErrType]


class JsonParser:
    def __init__(self, log_level_key: str | list[str] = 'level',
                 stderr_log_levels: Optional[List[str]] = None,
                 full_stdout: bool = True,
                 dict_output: bool = False,
                 skips: list[str] = None,
                 skips_warns: bool = False):
        self.log_level_key = log_level_key
        self.stderr_log_levels = stderr_log_levels or [
            LogLevels.PANIC, LogLevels.FATAL,
            LogLevels.ERROR, LogLevels.WARNING
        ]
        self.skips = skips or []
        self.full_stdout = full_stdout
        self.json_output = False
        self.dict_output = dict_output
        self.skips_warns = skips_warns

    def should_skips(self, log_line: str) -> bool:
        for skip in self.skips:
            if re.search(skip, log_line) or skip in log_line:
                if self.skips_warns:
                    warn('Skipping log line: {}'.format(log_line))
                return True
        return False

    def format_output(self, log_line: str) -> str | dict:
        if self.dict_output:
            return json.loads(log_line)
        return log_line

    def format_raw_output(self, log_line: str) -> str | dict:
        if self.dict_output:
            return {'raw': log_line}
        return log_line

    def append_records(self, stdout: list, stderr: list, record: str | dict, is_error: bool):
        if is_error:
            stderr.append(record)
            if self.full_stdout:
                stdout.append(record)
        else:
            stdout.append(record)

    def parse_output_to_json(self, logs: bytes) -> OutputType:
        stdout = []
        stderr = []

        log_strs = logs.decode('utf-8').split('\n')
        for log_line in log_strs:
            log_line = log_line.strip()
            if log_line:
                if self.should_skips(log_line):
                    record = self.format_raw_output(log_line)
                    stdout.append(record)
                    continue

                try:
                    json_obj = json.loads(log_line)
                    json_str = json.dumps(json_obj, ensure_ascii=False)
                    log_level = json_obj[self.log_level_key]

                    is_error = log_level in self.stderr_log_levels

                    record = self.format_output(json_str)
                    self.append_records(stdout=stdout, stderr=stderr, record=record, is_error=is_error)

                except json.JSONDecodeError:
                    record = self.format_raw_output(log_line)
                    self.append_records(stdout=stdout, stderr=stderr, record=record, is_error=True)

        return stdout, stderr


json_parser = JsonParser()

TCommandResult = TypeVar('TCommandResult', bound=CommandResult)


class CommonJsonCli(Generic[TCommandResult]):
    """
    Client for executing commands in Docker containers with JSON log parsing.

    See docs/CLI_USAGE.md for detailed documentation and examples.
    """
    def __init__(
        self,
        parse_json_logs: Callable[[bytes], OutputType] = json_parser.parse_output_to_json,
        result_factory: Type[TCommandResult] = CommandResult,
        cli_client: TheUberCompose = None,
    ):
        self._cli_client: TheUberCompose = cli_client or TheUberCompose()
        self._parse_json_logs = parse_json_logs
        self._result_factory = result_factory

    def _make_result(self, cmd: str, env: dict[str, str], logs: bytes, **kwargs) -> TCommandResult:
        stdout, stderr = self._parse_json_logs(logs)
        return self._result_factory(stdout=stdout, stderr=stderr, cmd=cmd, env=env, **kwargs)

    async def exec(self,
                   container: str,
                   command: str,
                   extra_env: dict[str, str] = None,
                   wait: Callable | ProcessExit | None = ProcessExit(),
                   command_result_extra: dict = None,
                   ) -> TCommandResult:
        if command_result_extra is None:
            command_result_extra = {}

        result = await self._cli_client.exec(
            container=container,
            command=command,
            extra_env=extra_env,
            wait=wait,
        )
        return self._make_result(
            cmd=command,
            env=extra_env or {},
            logs=result.stdout,
            **command_result_extra,
        )
