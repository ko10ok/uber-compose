# CommonJsonCli Usage Guide

`CommonJsonCli` is a client for executing commands in Docker containers with automatic JSON log parsing and error handling.

## Table of Contents
- [Basic Usage](#basic-usage)
- [Extended Command Result](#extended-command-result)
- [Custom JSON Parser](#custom-json-parser)
- [CommandResult](#commandresult)
- [JsonParser Configuration](#jsonparser-configuration)

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

```python
async def run_with_env(self) -> CommandResult:
    return await self.exec(
        container='app_container',
        command='my-app',
        extra_env={'DEBUG': 'true', 'LOG_LEVEL': 'debug'}
    )
```

---

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

### Methods

- **`has_no_errors()`**: Returns `True` if `stderr` is empty

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
from dataclasses import dataclass
from uber_compose import CommonJsonCli, CommandResult, JsonParser

@dataclass
class MyCommandResult(CommandResult):
    execution_time: float = 0.0

class AppCli(CommonJsonCli[MyCommandResult]):
    def __init__(self):
        self.container = 'my_app'
        
        # Configure parser
        parser = JsonParser(
            dict_output=True,
            stderr_log_levels=['error', 'fatal'],
            skips=[r'health_check']
        )
        
        super().__init__(
            parse_json_logs=parser.parse_output_to_json,
            result_factory=MyCommandResult
        )
    
    async def process_data(self, data_path: str) -> MyCommandResult:
        import time
        start = time.time()
        
        result = await self.exec(
            container=self.container,
            command=f'process --file {data_path}',
            extra_env={'LOG_FORMAT': 'json'},
            command_result_extra={
                'execution_time': time.time() - start
            }
        )
        
        return result

# Usage
cli = AppCli()
result = await cli.process_data('/data/input.csv')

if result.has_no_errors():
    print(f"Processing completed in {result.execution_time:.2f}s")
    for log in result.stdout:
        if isinstance(log, dict) and log.get('level') == 'info':
            print(f"INFO: {log.get('msg')}")
else:
    print("Errors encountered:")
    for error in result.stderr:
        print(error)
```

---

## Testing

Example test scenario:

```python
import vedro
from unittest.mock import AsyncMock, Mock
from d42 import schema

class Scenario(vedro.Scenario):
    subject = 'run command through CommonJsonCli'

    def given_mocked_client(self):
        self.cli_client_mock = Mock()
        self.result_logs = b'{"level": "info", "msg": "Success"}'
        self.mock_exec_result = Mock(stdout=self.result_logs)
        self.cli_client_mock.exec = AsyncMock(return_value=self.mock_exec_result)

    def given_common_json_cli(self):
        self.json_cli = CommonJsonCli(cli_client=self.cli_client_mock)

    async def when_user_executes_command(self):
        self.result = await self.json_cli.exec(
            container='test_container',
            command='echo "test"'
        )

    def then_result_should_contain_parsed_stdout(self):
        assert self.result.stdout == schema.list([
            schema.str.contains('Success')
        ]).len(1)
```
