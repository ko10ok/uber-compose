# Parallel Runs and Current Env API

This page describes how to run scenarios in parallel and how to read the
current environment / worker identifiers from user code.

## Enabling parallel runs

Parallel execution is provided by the `VedroUberComposeParallel` plugin. It
works together with the regular `VedroUberCompose` plugin.

```python
import vedro

from uber_compose import (
    ComposeConfig,
    DEFAULT_COMPOSE,
    VedroUberCompose,
    VedroUberComposeParallel,
)


class Config(vedro.Config):
    class Plugins(vedro.Config.Plugins):
        class UberCompose(VedroUberCompose):
            enabled = True
            compose_cfgs = {
                DEFAULT_COMPOSE: ComposeConfig(
                    compose_files="docker-compose.yaml",
                    # namespaces (replicas) per env description
                    env_parallelism={"env-a": 2, "env-b": 5, "env-c": 1},
                    default_env_parallelism=1,
                ),
            }

        class UberComposeParallel(VedroUberComposeParallel):
            enabled = True
```

Parallelism is configured **per environment** through `env_parallelism`. Each
env can have its own value, including `1` (a single replica/worker for that
env):

```python
env_parallelism={"env-a": 2, "env-b": 5, "env-c": 1}
default_env_parallelism=1
```

For every env the parent starts exactly `env_parallelism[env]` replicas
(`default_env_parallelism` is used for envs omitted from the mapping), one
worker per `(env, replica)`. Scenarios of an env are split across its replicas
round-robin, and every worker attaches to its own `env_id`.

## Reading identifiers from user code

All getters are available on `TheUberCompose`. They read a per-process
context that the plugin fills before every scenario, so they can be called
from scenarios, helpers and clients.

```python
from uber_compose import TheUberCompose

class Scenario(vedro.Scenario):
    env = Envs.API

    def then_it_should_use_its_own_namespace(self):
        client = TheUberCompose()

        # environment
        env_id = client.current_env_id()          # e.g. "w1-a1b2" or "default_env_id"
        namespace = client.current_namespace()    # human-readable namespace key
        env = client.current_env()                # Environment instance (or None)

        # worker / flow parameters
        worker_id = client.current_worker_id()
        workers_total = client.current_workers_total()
        is_parallel = client.is_current_worker_parallel()
        replica_index = client.current_replica_index()
        replicas_total = client.current_replicas_total()
        groups = client.current_worker_groups()
        run_id = client.current_run_id()
```

Because the methods are static, they can also be called without creating the
singleton instance:

```python
from uber_compose import TheUberCompose

env_id = TheUberCompose.current_env_id()
```

### Service env parameters

`current_env()` returns the environment instance whose service names are already
resolved for the current namespace. Service env values are available as well:

```python
db_name = TheUberCompose.current_service_env_param("db", "POSTGRES_DB")
db_env = TheUberCompose.current_service_env("db")  # dict with all params
```

This is the recommended way to parameterize database names, clients, keys, etc.
per environment/worker.

### Quick reference

| Method | Description |
|---|---|
| `current_env_id()` | Current namespace id |
| `current_env()` | Current `Environment` instance or `None` |
| `current_service_env(service)` | Dict of env parameters for a template service |
| `current_service_env_param(service, param, default=None)` | Single env parameter |
| `current_worker_id()` | Worker index |
| `current_workers_total()` | Total workers |
| `is_current_worker_parallel()` | `True` when more than one worker is running |
| `current_replica_index()` | Replica index within the env, or `None` |
| `current_replicas_total()` | Replicas for the current env, or `None` |
| `current_namespace()` | Namespace key for the current environment |
| `current_worker_groups()` | Env group keys assigned to this worker |
| `current_run_id()` | Run id used for `[[test_run_id]]` substitution |

## Parameterization placeholders

Placeholders are resolved both in service env parameters and in `x-migration`
commands. They are the declarative counterpart of the `TheUberCompose`
current-env API (see `uber_compose/helpers/parameterization.py`).

Supported placeholders:

- `[[env_id]]` — current environment id (namespace);
- `[[namespace]]` — current namespace key (same as `env_id` today);
- `[[worker_id]]` — current worker index (`0` when a single worker runs);
- `[[test_run_id]]` — current run id;
- `[[<service>]]` — actual (namespaced) service name, e.g. `[[postgres]]` ->
  `postgres-w1-a1b2`.

```python
Environment(
    Service("api", env=Env({
        "DB_HOST": "[[postgres]]",
        "DB_NAME": "app_[[env_id]]",
        "WORKER": "w[[worker_id]]",
    })),
    Service("postgres"),
    description="env-a",
)
```

The same placeholders can be used in migrations:

```yaml
services:
  api:
    x-migration:
      - after_start: sh -c 'echo "[[env_id]]:[[s1]]" >> /tmp/migration.log'
```

## Notes and limitations

- The parent process starts all replicas before workers, then workers attach
  to their `env_id`; workers do not tear down other namespaces.
- In parallel mode each env group is assigned to its own worker(s) by
  `(env, replica)`, so `env_parallelism` controls both replica count and the
  number of workers for that env.
- The parallel report currently contains scenario statuses, timings and counts.
  Step details, tracebacks and artifacts are not reconstructed yet.
- `current_env_id()` lives in a `ContextVar`; it is propagated to the
  scenario and async tasks within the same worker process, but not to arbitrary
  child processes or threads.
