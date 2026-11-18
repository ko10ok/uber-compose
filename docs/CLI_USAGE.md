# CommonJsonCli Usage Guide

`CommonJsonCli` is a client for executing commands in Docker containers with automatic JSON log parsing and error handling.

## Table of Contents
- [Basic Usage](#basic-usage)
- [Execution Modes](#execution-modes)
- [Extended Command Result](#extended-command-result)
- [Custom JSON Parser](#custom-json-parser)
- [CommandResult](#commandresult)
- [JsonParser Configuration](#jsonparser-configuration)
- [ExecLifeCyclePolicy](#execlifecyclepolicy)
- [Exec Strategies](#exec-strategies)
- [Timeouts Redefinition](#timeouts-redefinition)

---

## Basic Usage

Create a CLI client by inheriting from `CommonJsonCli`:

```python
from uber_compose import CommonJsonCli, CommandResult

class MyCli(CommonJsonCli):
    def __init__(self):
        self.container = 'app_container'
        super().__init__()

    async def run_command(self) -> CommandResult:
        return await self.exec(
            container=self.container,
            command='my-app --option value',
        )

# Usage
cli = MyCli()
result = await cli.run_command()

# Access results
print(result.stdout)  # list of parsed JSON logs or strings
print(result.stderr)  # list of error logs
print(result.has_no_errors())  # True if no errors
```

### With Environment Variables

By default, any executed command uses env variables set in container. 
You can override it by adding extra environment variables via extra_env.

```python
async def run_with_env(self) -> CommandResult:
    return await self.exec(
        container='app_container',
        command='my-app',
        extra_env={'DEBUG': 'true', 'LOG_LEVEL': 'debug'}
    )
```

---

### Setup Container For All Commands

```python
from uber_compose import CommonJsonCli, CommandResult

class MyCli(CommonJsonCli):
    def __init__(self):
        super().__init__(container = 'app_container')

    async def run_command(self) -> CommandResult:
        return await self.exec(command='my-app --option value')
    
    async def run_another_command(self) -> CommandResult:
        return await self.exec(command='my-app-another-part --any-option value2')

```

## Execution Modes

By default, `exec()` waits until the process exits.
`wait` controls when `exec()` returns; `life_cycle_policy` controls whether a still-running command is stopped.

| Mode | Call | `exit_code` | `waiting_done_successfully` | `has_no_errors()` |
|---|---|---|---|---|
| Wait until exit (default) | `wait` omitted (`wait=ProcessExit()` by default) | actual `int` | `True` | `exit_code == 0` and `stderr == []` |
| Wait until exit, timeout | `wait` omitted, `timeout=...` | `None` | `False` | `False` |
| Detached, don't wait | `wait=None`, `kill_after_command_still_running=False` | `None` | `True` — wait was skipped on purpose, not failed | `False` — exit code is unknown;<br>check log errors explicitly: `result.stderr == []` |
| Detached with `&` | command ends with `&` (same as `wait=None`) | `None` | `True` — wait was skipped on purpose, not failed | `False` — exit code is unknown;<br>check log errors explicitly: `result.stderr == []` |
| Wait condition met, process stopped | callable returns `True` while process runs | `TerminatedByCondition(143/137/0)` | `True` | `True` if `stderr == []` |
| Wait condition met, process exited by itself | callable returns `True` after exit | actual `int` | `True` | `exit_code == 0` and `stderr == []` |
| Wait condition not met | callable returns `False` | `None` | `False` | `False` |

`stderr != []` makes `has_no_errors()` fail in every mode.

A trailing `&` also switches to detached mode, including inside `sh -c`:

```python
from time import sleep
from uber_compose import ExecLifeCyclePolicy

# Default: wait until the command exits
result = await cli.exec(command='my-app')
# exit_code=0 | waiting_done_successfully=True | stderr=[]
assert result.has_no_errors()

# Detached: return immediately, keep the process running
result = await cli.exec(
    command='my-worker',
    wait=None,
    life_cycle_policy=ExecLifeCyclePolicy(
        kill_after_command_still_running=False,
    ),
)
# exit_code=None | waiting_done_successfully=True | stderr=[]
assert not result.has_no_errors()  # no exit code to verify

# Wait for a condition; stop the process when it is met
result = await cli.exec(
    command='tail -f /dev/null',
    wait=lambda *_: sleep(1) or True,
)
# exit_code=TerminatedByCondition(143) | waiting_done_successfully=True | stderr=[]
assert result.has_no_errors()
```

`TerminatedByCondition` is an `int` subclass used when the process was stopped because the `wait` condition returned `True`. It is truthy even for `TerminatedByCondition(0)`.

## Extended Command Result

Extend `CommandResult` to add custom fields:

```python
from dataclasses import dataclass
from uber_compose import CommonJsonCli, CommandResult

@dataclass
class ExtendedCommandResult(CommandResult):
    config_data: dict = None
    metadata: str = ""

class MyCli(CommonJsonCli[ExtendedCommandResult]):
    def __init__(self):
        self.container = 'app_container'
        super().__init__(result_factory=ExtendedCommandResult)

    async def run_with_config(self, config: dict) -> ExtendedCommandResult:
        return await self.exec(
            container=self.container,
            command='my-app',
            command_result_extra={
                'config_data': config,
                'metadata': 'custom_metadata'
            }
        )

# Usage
cli = MyCli()
result = await cli.run_with_config({'key': 'value'})

# Access extended fields
print(result.config_data)  # {'key': 'value'}
print(result.metadata)     # 'custom_metadata'
```

---

## Custom JSON Parser

Configure JSON parsing behavior with `JsonParser`:

### String Output (default)

```python
from uber_compose import CommonJsonCli, JsonParser

parser = JsonParser()
cli = CommonJsonCli(parse_json_logs=parser.parse_output_to_json)
```

Output example:
```python
result.stdout = [
    '{"level": "info", "msg": "Started"}',
    '{"level": "debug", "msg": "Processing"}'
]
```

### Dictionary Output

```python
parser = JsonParser(dict_output=True)
cli = CommonJsonCli(parse_json_logs=parser.parse_output_to_json)
```

Output example:
```python
result.stdout = [
    {'level': 'info', 'msg': 'Started'},
    {'level': 'debug', 'msg': 'Processing'}
]
```

### Custom Error Levels

```python
parser = JsonParser(
    stderr_log_levels=['error', 'fatal', 'critical']
)
cli = CommonJsonCli(parse_json_logs=parser.parse_output_to_json)
```

### Skip Log Lines

Skip logs by substring or regex pattern:

```python
parser = JsonParser(
    skips=['debug_info', r'^\[TRACE\]'],
    skips_warns=True  # Warn when skipping
)
cli = CommonJsonCli(parse_json_logs=parser.parse_output_to_json)
```

Skipped logs appear in `stdout` as raw strings (or `{'raw': 'log_line'}` with `dict_output=True`).

### Full Stdout Control

```python
# Default: errors appear in both stdout and stderr
parser = JsonParser(full_stdout=True)

# Errors only in stderr
parser = JsonParser(full_stdout=False)
```

### Custom Log Level Key

```python
# Default key is 'level'
parser = JsonParser(log_level_key='severity')

# For logs like: {"severity": "error", "msg": "Failed"}
```

### Combined Configuration

```python
parser = JsonParser(
    log_level_key='level',
    stderr_log_levels=['error', 'fatal', 'panic'],
    full_stdout=True,
    dict_output=True,
    skips=['debug_verbose', r'^\[INTERNAL\]'],
    skips_warns=False
)

cli = CommonJsonCli(parse_json_logs=parser.parse_output_to_json)
```

---

## CommandResult

### Fields

- **`stdout`**: `list[str | dict]` - Parsed output logs
- **`stderr`**: `list[str | dict]` - Error logs (based on log level)
- **`cmd`**: `str` - Executed command
- **`env`**: `dict[str, str]` - Environment variables used
- **`exit_code`**: `int | None` - Application exit code; `None` if the process did not finish
- **`waiting_done_successfully`**: `bool` - `False` when a timeout or unmet wait condition interrupted waiting

### `has_no_errors()`

Returns `self`; the check itself happens through `__bool__`. It passes only when:

1. `stderr == []`;
2. `waiting_done_successfully is True`;
3. `exit_code` is `TerminatedByCondition`, or `exit_code == 0`.

### Example

```python
result = await cli.exec(container='app', command='my-cmd')

if result.has_no_errors():
    print("Success!")
    for log in result.stdout:
        print(log)
else:
    print("Errors occurred:")
    for error in result.stderr:
        print(error)
```

---

## JsonParser Configuration

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `log_level_key` | `str \| list[str]` | `'level'` | Key name for log level in JSON |
| `stderr_log_levels` | `list[str]` | `['panic', 'fatal', 'error', 'warning']` | Log levels to route to stderr |
| `full_stdout` | `bool` | `True` | Include errors in stdout |
| `dict_output` | `bool` | `False` | Output as dicts instead of strings |
| `skips` | `list[str]` | `[]` | Patterns to skip (substring or regex) |
| `skips_warns` | `bool` | `False` | Warn when skipping logs |

### Log Levels

Predefined in `LogLevels` class:
- `TRACE`, `DEBUG`, `INFO`, `WARNING`, `ERROR`, `FATAL`, `PANIC`

### Non-JSON Logs

Non-JSON lines are treated as errors and:
- Added to `stderr`
- Optionally added to `stdout` (if `full_stdout=True`)
- Formatted as raw strings or `{'raw': 'line'}` (if `dict_output=True`)

---

## Complete Example

```python
import time

from dataclasses import dataclass
from uber_compose import CommonJsonCli, CommandResult, JsonParser


@dataclass
class MyCommandResult(CommandResult):
    start_time: float = 0.0

class AppCli(CommonJsonCli[MyCommandResult]):
    def __init__(self):        
        # Configure parser
        parser = JsonParser(
            dict_output=True,
            stderr_log_levels=['error', 'fatal'],
            skips=[r'health_check']
        )
        
        super().__init__(
            container = 'my_app',
            parse_json_logs=parser.parse_output_to_json,
            result_factory=MyCommandResult
        )
    
    async def process_data(self, data_path: str) -> MyCommandResult:
        result = await self.exec(
            command=f'process --file {data_path}',
            extra_env={'LOG_FORMAT': 'json'},
            command_result_extra={
                'start_time': time.time()
            }
        )
        
        return result

# Usage
cli = AppCli()
result = await cli.process_data('/data/input.csv')

assert result.has_no_errors()
```

## ExecLifeCyclePolicy

`ExecLifeCyclePolicy` controls the execution behavior of commands to optimize performance and resource usage. It allows you to skip certain phases of the command execution lifecycle.

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `kill_before_same_old_command_running` | `bool` | `True` | Kill the previous instance of the same command if it is still running before executing a new one |
| `kill_after_command_still_running` | `bool` | `True` | Kill the command if it is still running after a timeout or after a wait condition is met |
| `break_on_timeout` | `bool` | `True` | Stop waiting and return early if the timeout is reached |

### Basic Usage

```python
from uber_compose import CommonJsonCli, ExecLifeCyclePolicy

class AppCli(CommonJsonCli):
    def __init__(self):                
        super().__init__(
            container='app',
            life_cycle_policy=ExecLifeCyclePolicy(
                kill_before_same_old_command_running=True,
                kill_after_command_still_running=True,
                break_on_timeout=True
            )
        )
```

### Override Policy Per Command

```python
from uber_compose import CommonJsonCli, CommandResult, ExecLifeCyclePolicy

class AppCli(CommonJsonCli):
    def __init__(self):                
        super().__init__(container='app')
        
    async def run_quick_command(self) -> CommandResult:
        return await self.exec(
            command='quick-task',
            life_cycle_policy=ExecLifeCyclePolicy(
                kill_before_same_old_command_running=False,
                kill_after_command_still_running=False,
            )
        )
```

### Disable Lifecycle Management

```python
# Disable killing old instances
policy = ExecLifeCyclePolicy(kill_before_same_old_command_running=False)

# Disable all lifecycle management
policy = ExecLifeCyclePolicy(
    kill_before_same_old_command_running=False,
    kill_after_command_still_running=False,
    break_on_timeout=False
)
```

## Exec Strategies

See [Alternative Exec Strategies](EXEC_STRATEGIES.md).

## Timeouts Redefinition

By default `CommonJsonCli` uses the following timeouts for command execution:

```python
from uber_compose import TimeOutCheck

timeout = TimeOutCheck(
    attempts=10, 
    delay_s=1
),
```

It's possible to redefine these timeouts in the `__init__` method of your CLI class:

```python
from uber_compose import CommonJsonCli, CommandResult, JsonParser, TimeOutCheck

class AppCli(CommonJsonCli):
    def __init__(self):                
        super().__init__(
            timeout = TimeOutCheck(
                attempts=10, 
                delay_s=1
            ),
        )
```

Or redefine only for specific command:

```python
import time

from uber_compose import CommonJsonCli, CommandResult, JsonParser, TimeOutCheck

class AppCli(CommonJsonCli):
    def __init__(self):                
        super().__init__(container='app')
        
    async def run_command_with_custom_timeout(self) -> CommandResult:
        return await self.exec(
            command='command',
            timeout = TimeOutCheck(
                attempts=50, 
                delay_s=2
            ),
        )
```
