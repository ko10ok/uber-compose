from enum import Enum
from time import perf_counter

from rich.console import Console
from rich.text import Text

from uber_compose.core.constants import Constants
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


# TODO collect all into file and on level in stdout
class Logger:
    def __init__(self, log_policy: LogPolicySet = None, cfg_constants=None):
        if cfg_constants is None:
            cfg_constants = Constants()
        if log_policy is None:
            log_policy = LogPolicy.presets().get(cfg_constants.default_log_policy)
        self.log_policy = log_policy
        self.stream = Console(highlight=False, force_terminal=True, markup=False, soft_wrap=True)
        self.debug = True

    def log(self, text: str | Text, level: LogEvents = LogEvents.GLOBAL_DEBUG, line_no=0):
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
