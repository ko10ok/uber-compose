from enum import Enum
from pathlib import Path
from time import perf_counter

from rich.console import Console
from rich.text import Text

from uber_compose.core.constants import Constants
from uber_compose.core.constants import cleanup_log_files
from uber_compose.output.styles import Style

CONSOLE = Console(highlight=False, force_terminal=True, markup=False, soft_wrap=True)


class LogEvents(Enum):
    STAGE = 'stage'
    STAGE_INFO = 'stage_info'
    STAGE_DETAILS = 'stage_details'
    STAGE_DEBUG = 'stage_debug'
    ERROR = 'error'
    ERROR_DETAILS = 'error_details'
    COMMANDS = 'commands'
    COMMAND_OUTPUT = 'command_output'
    SYSTEM_COMMANDS = 'system_commands'
    SYSTEM_COMMANDS_OUTPUT = 'system_commands_output'
    SYSTEM_COMMANDS_DEBUG = 'system_commands_debug'
    SYSTEM_COMMANDS_ENVIRONMENT_DEBUG = 'system_commands_environment_debug'
    GLOBAL_DEBUG = 'global_debug'


class LogPolicySet:
    def __init__(self, *levels: LogEvents):
        self.levels = levels

    def __contains__(self, item: str | LogEvents):
        return item in self.levels

    def __repr__(self):
        return f'LogPolicy([{", ".join(level.value for level in self.levels)}])'


class LogPolicy:
    DEFAULT = LogPolicySet(LogEvents.STAGE, LogEvents.ERROR)
    DEFAULT_FILE = LogPolicySet(
        LogEvents.STAGE, LogEvents.STAGE_INFO, LogEvents.STAGE_DETAILS, LogEvents.ERROR,
    )
    VERBOSE = LogPolicySet(
        LogEvents.STAGE, LogEvents.STAGE_INFO, LogEvents.STAGE_DETAILS,
        LogEvents.ERROR, LogEvents.COMMANDS, LogEvents.COMMAND_OUTPUT,
    )
    DEBUG = LogPolicySet(LogEvents.GLOBAL_DEBUG)

    @staticmethod
    def presets() -> dict[str, LogPolicySet]:
        return {
            'DEFAULT': LogPolicy.DEFAULT,
            'VERBOSE': LogPolicy.VERBOSE,
            'DEBUG': LogPolicy.DEBUG,
        }


class StageTimer:
    def __init__(self, logger: "Logger", text: str | Text, level: LogEvents):
        self._logger = logger
        self._text = text
        self._level = level
        self._started_at = perf_counter()
        self._done = False

    @property
    def description(self) -> str:
        return self._text.plain if isinstance(self._text, Text) else str(self._text)

    def _complete(self, marker: str, style: str) -> None:
        if self._done:
            return
        self._done = True
        elapsed = perf_counter() - self._started_at
        self._logger.log(
            Text(f' {marker} {self.description} ({elapsed:.2f}s)', style=style),
            self._level,
        )

    def done(self) -> None:
        self._complete('✔', Style.good)

    def failed(self) -> None:
        self._complete('✖', Style.bad)

    def __enter__(self) -> "StageTimer":
        return self

    def __exit__(self, exc_type, exc, traceback) -> bool:
        if exc_type is None:
            self.done()
        else:
            self.failed()
        return False


class Logger:
    def __init__(self,
                 log_policy: LogPolicySet = None,
                 cfg_constants=None,
                 file_log_policy: LogPolicySet | str | None = LogPolicy.DEFAULT_FILE,
                 ):
        if cfg_constants is None:
            cfg_constants = Constants()
        if log_policy is None:
            log_policy = LogPolicy.presets().get(cfg_constants.default_log_policy)
        self.log_policy = log_policy
        self.stream = Console(highlight=False, force_terminal=True, markup=False, soft_wrap=True)
        self.debug = True

        if isinstance(file_log_policy, str):
            file_log_policy = LogPolicy.presets()[file_log_policy.upper()]
        self.file_log_policy = file_log_policy

        self.log_file_path = Path(
            getattr(cfg_constants, 'log_file_path', None)
            or 'uber-compose.log'
        )
        self.file_stream = None
        if self.file_log_policy is not None:
            self.log_file_path.parent.mkdir(parents=True, exist_ok=True)
            cleanup_log_files(
                self.log_file_path,
                getattr(cfg_constants, 'log_files_limit', None),
                keep=self.log_file_path,
            )
            self.file_stream = open(self.log_file_path, 'w', encoding='utf-8')

    def _file_log_enabled(self, level: LogEvents) -> bool:
        if self.file_stream is None:
            return False
        if LogEvents.GLOBAL_DEBUG in self.file_log_policy:
            return True
        return level in self.file_log_policy

    def _write_file_log_raw(self, text: str | Text) -> None:
        if self.file_stream is None:
            return
        plain_text = text.plain if isinstance(text, Text) else str(text)
        self.file_stream.write(f'{plain_text}\n')
        self.file_stream.flush()

    def _write_file_log(self, text: str | Text, level: LogEvents) -> None:
        if not self._file_log_enabled(level):
            return
        self._write_file_log_raw(text)

    def write_file_log(self, text: str | Text, level: LogEvents | None = None) -> None:
        """Write to the log file directly.

        Without a level the record bypasses the file log policy. It is used for
        diagnostics that must be kept whenever file logging is enabled, such as
        logs of services that failed to start.
        """
        if self.file_stream is None:
            return
        if level is not None and not self._file_log_enabled(level):
            return
        self._write_file_log_raw(text)

    def log(self, text: str | Text, level: LogEvents = LogEvents.GLOBAL_DEBUG, line_no=0):
        self._write_file_log(text, level)

        if LogEvents.GLOBAL_DEBUG in self.log_policy:
            if line_no == 0:
                self.stream.print(f'{level}:', style='bold grey15 on green', end='')
                self.stream.print('', style='white on default')
            self.stream.print(text)
            return

        elif level in self.log_policy:
            self.stream.print(text)

    def _start_stage(self, text: str | Text, level: LogEvents, **kwargs) -> "StageTimer":
        self.log(text, level, **kwargs)
        return StageTimer(self, text, level)

    def stage(self, text: str | Text, **kwargs) -> "StageTimer":
        return self._start_stage(text, LogEvents.STAGE, **kwargs)

    def stage_info(self, text: str | Text, **kwargs) -> "StageTimer":
        return self._start_stage(text, LogEvents.STAGE_INFO, **kwargs)

    def error(self, text: str | Text, **kwargs):
        self.log(text, LogEvents.ERROR, **kwargs)

    def error_details(self, text: str | Text, **kwargs):
        self.log(text, LogEvents.ERROR_DETAILS, **kwargs)

    def stage_details(self, text: str | Text, **kwargs) -> "StageTimer":
        return self._start_stage(text, LogEvents.STAGE_DETAILS, **kwargs)

    def stage_debug(self, text: str | Text, **kwargs) -> "StageTimer":
        return self._start_stage(text, LogEvents.STAGE_DEBUG, **kwargs)

    def commands(self, text: str | Text, **kwargs):
        self.log(text, LogEvents.COMMANDS, **kwargs)

    def command_output(self, text: str | Text, **kwargs):
        self.log(text, LogEvents.COMMAND_OUTPUT, **kwargs)

    def system_commands(self, text: str | Text, **kwargs):
        self.log(text, LogEvents.SYSTEM_COMMANDS, **kwargs)

    def system_commands_output(self, text: str | Text, **kwargs):
        self.log(text, LogEvents.SYSTEM_COMMANDS_OUTPUT, **kwargs)

    def system_commands_debug(self, text: str | Text, **kwargs):
        self.log(text, LogEvents.SYSTEM_COMMANDS_DEBUG, **kwargs)

    def system_commands_environment_debug(self, text: str | Text, **kwargs):
        self.log(text, LogEvents.SYSTEM_COMMANDS_ENVIRONMENT_DEBUG, **kwargs)
