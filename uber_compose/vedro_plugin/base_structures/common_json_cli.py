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

from uber_compose.uber_compose import SystemUberCompose

from uber_compose.core.docker_compose_shell.interface import ProcessExit
from uber_compose.uber_compose import TheUberCompose


@dataclass
class CommandResult:
    stdout: list
    stderr: list
    cmd: str
    env: dict[str, str]

    def _format_value(self, key, value, indent_level=1, print_new_line=True):
        """Formats value considering its type and nesting level."""
        indent = "    " * indent_level

        if key:
            field_name_len = len(indent) + len(key) + len(" = ")
            prefix = f"{indent}{key} = "
        else:
            field_name_len = 0
            prefix = ""

        if isinstance(value, str):
            if print_new_line and '\n' in value:
                # Multiline string with triple quotes
                lines = value.split('\n')
                continuation_indent = " " * field_name_len
                formatted_lines = ["'''"] + [f"{continuation_indent}{line}" for line in lines] + [
                    f'{continuation_indent}' + "'''"]
                return prefix + "\n".join(formatted_lines)
            # Single-line string with single quotes
            return prefix + f"'{value}'"

        elif isinstance(value, list):
            if len(value) == 0:
                # Empty list on a single line
                return prefix + "[]"
            elif len(value) == 1:
                # Single-element list - check if multiline formatting is needed
                item = value[0]
                if isinstance(item, dict) and len(item) > 2:
                    # Dict with 3+ keys - multiline format
                    formatted_item = self._format_value(None, item, indent_level + 1)
                    return prefix + "[\n" + f"{indent}    {formatted_item}\n{indent}]"
                else:
                    # Simple element - single-line format
                    return prefix + repr(value)
            else:
                # Multiline output for lists with length > 1
                items = [f"{indent}    {self._format_value(None, item, indent_level + 1)}" for item in value]
                return prefix + "[\n" + ",\n".join(items) + f"\n{indent}]"

        elif isinstance(value, dict):
            if len(value) <= 2:
                # Single line for dicts with <= 2 keys
                return prefix + repr(value)
            else:
                # Multiline output for dicts with > 2 keys
                items = [
                    f"{indent}    {repr(k)}: {self._format_value(None, v, indent_level + 1)}"
                    for k, v in value.items()
                ]
                return prefix + "{\n" + ",\n".join(items) + f"\n{indent}}}"

        else:
            return prefix + repr(value)

    def __str__(self):
        stderr_key = "stderr"
        if not self._has_no_errors():
            stderr_key = "❌ stderr"
        fields = [
            self._format_value("stdout", self.stdout),
            self._format_value(stderr_key, self.stderr),
            self._format_value("cmd", self.cmd, print_new_line=True),
            self._format_value("env", self.env),
        ]

        return f"{self.__class__.__name__}(\n" + ",\n".join(fields) + "\n)"

    def _has_no_errors(self) -> bool:
        return self.stderr == []

    def __bool__(self):
        has_no_errors = self._has_no_errors()
        if not has_no_errors:
            raise AssertionError(f'Command result contains errors:\n {str(self)}')
        return True

    def has_no_errors(self):
        return self


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
        cli_client: SystemUberCompose = None,
    ):
        self._cli_client: SystemUberCompose = cli_client or TheUberCompose()
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
