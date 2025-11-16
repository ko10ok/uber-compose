import json
import re
from dataclasses import dataclass
from typing import Callable
from typing import List
from typing import Optional
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


OutputType = tuple[list[str], list[str]]


class JsonParser:
    def __init__(self, log_level_key: str = 'level',
                 full_stdout: bool = True,
                 stderr_log_levels: Optional[List[str]] = None,
                 skips: list[str] = None):
        self.log_level_key = log_level_key
        self.stderr_log_levels = stderr_log_levels or [
            LogLevels.PANIC, LogLevels.FATAL,
            LogLevels.ERROR, LogLevels.WARNING
        ]
        self.skips = skips or []
        self.full_stdout = full_stdout

    def parse_output_to_json(self, logs: bytes) -> OutputType:
        stdout = []
        stderr = []

        log_strs = logs.decode('utf-8').split('\n')
        for log_line in log_strs:
            log_line = log_line.strip()
            if log_line:
                try:
                    json_obj = json.loads(log_line)
                    json_str = json.dumps(json_obj, ensure_ascii=False)
                    log_level = json_obj.get(self.log_level_key, None)
                    if log_level is None or log_level in self.stderr_log_levels:
                        stderr.append(json_str)
                        if self.full_stdout:
                            stdout.append(json_str)
                    else:
                        stdout.append(json_str)
                except json.JSONDecodeError:
                    for skip in self.skips:
                        if re.search(skip, log_line) or skip in log_line:
                            warn('Skipping log line: {}'.format(log_line))
                            break
                    else:
                        if self.full_stdout:
                            stdout.append(log_line)
                        stderr.append(log_line)
        return stdout, stderr


json_parser = JsonParser()


class CommonJsonCli:
    def __init__(
        self,
        parse_json_logs: Callable[[bytes], tuple[list[str | dict], list[str | dict]]] = json_parser.parse_output_to_json,
        cli_client: TheUberCompose = None
    ):
        self._cli_client: TheUberCompose = cli_client or TheUberCompose()
        self._parse_json_logs = parse_json_logs

    def _make_result(self, cmd: str, env: dict[str, str], logs: bytes) -> CommandResult:
        stdout, stderr = self._parse_json_logs(logs)
        return CommandResult(stdout=stdout, stderr=stderr, cmd=cmd, env=env)

    async def exec(self,
                   container: str,
                   command: str,
                   extra_env: dict[str, str] = None,
                   wait: Callable | ProcessExit | None = ProcessExit(),
                   ) -> CommandResult:
        result = await self._cli_client.exec(
            container=container,
            command=command,
            extra_env=extra_env,
            wait=wait,
        )
        return self._make_result(
            cmd=command,
            env=extra_env or {},
            logs=result.stdout
        )
