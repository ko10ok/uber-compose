# Alternative Exec Strategies

Pass a strategy class through the `exec` parameter:

```python
from uber_compose import PidofExecStrategy, StatusFileExecStrategy

await cli.exec(command='my-app', exec=StatusFileExecStrategy)  # default
await cli.exec(command='my-app', exec=PidofExecStrategy)       # legacy pidof checks
```

`StatusFileExecStrategy` returns the application exit code.
`PidofExecStrategy` returns `exit_code=None` because the legacy path does not
collect it. A nonzero exit code is a normal result, not an exception.

## Writing a Strategy

A strategy is any class with `async execute(context)` returning `ExecResult`
or `ExecTimeout`. Subclassing `ExecStrategy` is optional.

```python
from uber_compose import ExecContext, ExecStrategy
from uber_compose.helpers.exec_result import ExecResult, ExecTimeout


class MyExecStrategy(ExecStrategy):
    async def execute(self, context: ExecContext) -> ExecResult | ExecTimeout:
        ...
```

`ExecContext` provides `shell`, `container` (resolved compose service name),
`command`, `extra_env`, `wait`, `timeout`, `life_cycle_policy`, `env`, `root`.

- `wait=ProcessExit()` — wait for completion and return the exit code.
- `wait=None` — return immediately with `exit_code=None`.
- `wait=<callable>` — call it; return `ExecTimeout` if it reports unfinished.
- `exit_code=None` means the process did not finish. There is no separate flag.
- Timeout budget is `timeout.attempts * timeout.delay_s`.

## Docker Engine API Example

Uses `docker-py` (`pip install docker`) and never calls the Docker CLI.

```python
import asyncio

from docker import DockerClient

from uber_compose import ExecContext
from uber_compose import ExecStrategy
from uber_compose import ProcessExit
from uber_compose.helpers.exec_result import ExecResult
from uber_compose.helpers.exec_result import ExecTimeout


class DockerApiExecStrategy(ExecStrategy):
    def __init__(self, base_url: str = 'unix:///var/run/docker.sock'):
        self._client = DockerClient(base_url=base_url)

    async def execute(self, context: ExecContext) -> ExecResult | ExecTimeout:
        container = await asyncio.to_thread(self._find_container, context.container)
        exec_id = await asyncio.to_thread(self._create_exec, container, context)

        if context.wait is None:
            await asyncio.to_thread(self._client.api.exec_start, exec_id, detach=True)
            return ExecResult(stdout=b'', cmd=context.command, exit_code=None)

        if context.wait != ProcessExit():
            raise NotImplementedError('Supports only ProcessExit and wait=None')

        try:
            stdout = await asyncio.wait_for(
                asyncio.to_thread(self._client.api.exec_start, exec_id, detach=False),
                timeout=self._timeout_s(context),
            )
        except asyncio.TimeoutError:
            return ExecTimeout(stdout=b'', cmd=context.command)

        exit_code = await asyncio.to_thread(
            lambda: self._client.api.exec_inspect(exec_id).get('ExitCode'),
        )
        return ExecResult(stdout=stdout, cmd=context.command, exit_code=exit_code)

    def _find_container(self, service_name: str):
        containers = self._client.containers.list(
            all=True,
            filters={'label': f'com.docker.compose.service={service_name}'},
        )
        if not containers:
            raise LookupError(f'Container for service {service_name!r} not found')
        return containers[0]

    def _create_exec(self, container, context: ExecContext) -> str:
        environment = [
            f'{key}={value}' for key, value in (context.extra_env or {}).items()
        ]
        return self._client.api.exec_create(
            container.id,
            ['sh', '-c', context.command],
            environment=environment,
        )['Id']

    @staticmethod
    def _timeout_s(context: ExecContext) -> float:
        if context.timeout is None:
            return 150.0
        return max(context.timeout.attempts * context.timeout.delay_s, 0.05)
```

Use `context.container` as a compose service name; lookup by the
`com.docker.compose.service` label works across compose projects.
Handle `kill_before`/`kill_after` from `context.life_cycle_policy` if needed.
