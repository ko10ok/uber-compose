# Parallel Runs

This page explains how uber-compose runs scenarios in parallel, how to enable it,
and which config to use for each common case.

## How parallelism works

Parallelism has two independent levels:

1. **Environments** — how many isolated env groups may exist at the same time.
2. **Workers** — how many processes run the scenarios of one environment.

Each worker gets its **own copy of the environment** with its own namespace.
Scenarios of an environment are split between its workers; different
environments run alongside each other.

```
                         ┌──────────────────────────────┐
                         │        parent vedro          │
                         │    builds the worker plan    │
                         └───────────────┬──────────────┘
                                         │
        ┌────────────────────────────────┼────────────────────────────────┐
        │                                │                                │
  ┌─────▼──────┐                  ┌──────▼─────┐                  ┌───────▼────┐
  │   env-a    │                  │   env-b    │                  │   env-c    │
  │ 3 workers  │                  │ 2 workers  │                  │ 1 worker   │
  └─────┬──────┘                  └──────┬─────┘                  └───────┬────┘
        │                                │                                │
  ┌─────┼─────┐                    ┌─────┴─────┐                          │
  ▼     ▼     ▼                    ▼           ▼                          ▼
 w0    w1    w2                   w0          w1                         w0
env-a env-a env-a                env-b       env-b                      env-c
w0    w1    w2                   w0          w1                         w0
ns:   ns:   ns:                  ns:         ns:                        ns:
a1    a2    a3                   b1          b2                         c1
```

- One **worker** = one process + one namespaced environment replica.
- `workers_per_env` says how many workers/replicas an env gets.
- `max_concurrent_envs` says whether envs may coexist or must rotate.
- `--uc-mt` is the runtime switch that starts worker processes. Without it
  scenarios run sequentially in one process.

---

## How to enable it

Enable both plugins in `vedro.cfg.py`:

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
                ),
            }

        class UberComposeParallel(VedroUberComposeParallel):
            enabled = True
```

Run with workers:

```bash
vedro run scenarios/ --uc-mt
```

Preview the execution plan without starting containers or workers:

```bash
vedro run scenarios/ --uc-mt --uc-mt-plan
```

The plan shows environments, services, workers/namespaces, and the first test
files assigned to each worker. Use `--uc-mt-plan=1` for namespaces and full test
lists, or `--uc-mt-plan=2` for full test paths.

### General parameters

| Parameter | Where | Meaning |
|---|---|---|
| `workers_per_env` | `ComposeConfig` | `{env_description: workers}`. Omitted or `{}` means `default_workers_per_env` for every env |
| `default_workers_per_env` | `ComposeConfig` | Default workers for an env; `1` by default |
| `max_concurrent_envs` | `ComposeConfig` | How many env groups may stay alive at once; `1` = sequential rotation |
| `multi_thread` | parallel plugin config | Same as `--uc-mt` |
| `worker_timeout` | parallel plugin config | Kill a worker after N seconds |
| `--uc-mt` | CLI | Enable parallel worker processes |
| `--uc-workers-per-env=N`, `--uc-wpe=N` | CLI | Override `workers_per_env` for every env, for this run only |
| `--uc-mt-plan[=LEVEL]` | CLI | Print the execution plan without starting containers or workers |

`workers_per_env` keys are environment descriptions. You can use the
`Environment` object or its description string:

```python
workers_per_env={Envs.API: 2, Envs.WORKER: 5}
# same as
workers_per_env={"api": 2, "worker": 5}
```

Descriptions must be unique: environments with the same description share one
key.

---

## Cases

### Case 1. Split scenarios of one environment across several workers

All scenarios use the same env, so split that env between workers.

```
env-a ──┬─ w0 → own namespace
        ├─ w1 → own namespace
        ├─ w2 → own namespace
        └─ w3 → own namespace
```

**Config:**

```python
ComposeConfig(
    compose_files="docker-compose.yaml",
    workers_per_env={"env-a": 4},
)
```

**Command:**

```bash
vedro run scenarios/ --uc-mt
```

**Result:** 4 namespaced copies of `env-a` and 4 workers. Scenarios of `env-a`
are split between them round-robin. The effective number of workers is capped
by the number of scenarios: `5` workers for an env with 3 scenarios produces
3 workers.

### Case 2. Run different environments at the same time

Scenarios use several envs; each gets one worker by default.

```
env-a ── w0 ─┐
env-b ── w0 ─┼─ run in parallel
env-c ── w0 ─┘
```

**Config:** nothing beyond the common setup.

**Command:**

```bash
vedro run scenarios/ --uc-mt
```

**Result:** every env gets `default_workers_per_env` workers (one by default),
and different envs run in parallel.

If there is only one env group, the plan has a single worker and scenarios run
in one process. Use Case 1 to split that env.

### Case 3. Use different worker counts per environment

Envs have different loads.

```
env-a ── w0 w1                    (2)
env-b ── w0 w1 w2 w3 w4           (5)
env-c ── w0                       (1)
```

**Config:**

```python
ComposeConfig(
    compose_files="docker-compose.yaml",
    workers_per_env={"env-a": 2, "env-b": 5, "env-c": 1},
    default_workers_per_env=1,
)
```

**Command:**

```bash
vedro run scenarios/ --uc-mt
```

**Result:** `2 + 5 + 1` replicas are started, each env's scenarios are split
between its own workers, and all workers run concurrently.

### Case 4. Give every environment the same number of workers

Use one global value for all envs.

```
env-a ── w0 w1 w2
env-b ── w0 w1 w2
env-c ── w0 w1 w2
```

**Config:**

```python
ComposeConfig(
    compose_files="docker-compose.yaml",
    default_workers_per_env=3,
)
```

**Command:**

```bash
vedro run scenarios/ --uc-mt
```

**Result:** every env gets 3 workers. Entries in `workers_per_env` still win
over this default.

### Case 5. Temporarily override workers for every environment

Override the configured worker counts for a single run.

```
config:          env-a ── w0
--uc-wpe=4:      env-a ── w0 w1 w2 w3
```

**Config:** unchanged.

**Command:**

```bash
vedro run scenarios/ --uc-mt --uc-wpe=4
```

**Result:** `--uc-wpe` overrides even explicit `workers_per_env` entries for
this run only. It is not available in `ComposeConfig`.

### Case 6. Control env rotation in sequential runs

Sequential runs either rotate envs or keep them alive.

```
max_concurrent_envs=1 — rotation
env-a ──▶ down ──▶ env-b ──▶ down ──▶ env-c

max_concurrent_envs=2 — coexistence
env-a ──────────────▶
env-b ──────────────▶
```

**Config:**

```python
ComposeConfig(
    compose_files="docker-compose.yaml",
    max_concurrent_envs=2,
)
```

**Command:**

```bash
vedro run scenarios/
```

**Result:**

- `max_concurrent_envs=1` (default): one env at a time. Before a scenario from
  another env starts, the previous non-singleton services are torn down and the
  required env is started — **env rotation**.
- `max_concurrent_envs>1`: envs may coexist and be reused; they are left
  running. This signals that the project supports multiple isolated namespaces.

`max_concurrent_envs` does not create workers. In parallel mode envs are always
namespaced and kept for their workers.

### Case 7. Share infrastructure with singletons

Share a heavy service between namespaced envs.

```
env-a w0  DB_NAME=app_a0 ─┐
env-a w1  DB_NAME=app_a1 ─┼──▶  db (singleton)
env-b w0  DB_NAME=app_b0 ─┘      started once, migrations once
```

Mark shared heavy services as singletons:

```python
from uber_compose import Environment, Service
from uber_compose.env_description.env_types import ServiceMode

Environment(
    Service("postgres", mode=ServiceMode.SINGLETON),
    Service("api", env=Env({"DB_NAME": "app_[[env_id]]"})),
    description="env-a",
)
```

- the singleton container is started once and is not renamed;
- its migrations run once;
- it is protected from per-namespace restarts, including env rotation;
- namespaced services reach it via `[[postgres]]`.

Use placeholders to isolate logical resources inside the shared service, for
example `DB_NAME=app_[[env_id]]` or `KAFKA_TOPIC_PREFIX=w[[worker_id]]_`. Without
logical isolation parallel tests can see each other's data.

Singletons fit infrastructure that supports namespacing by
database/schema/topic/prefix. They do not fit stateful services whose state
tests cannot isolate.

---

# Reference

## Flags

| Flag | Meaning | When to use |
|---|---|---|
| `--uc-mt` | Master switch: create parallel worker processes | Always, when you want any parallelism |
| `--uc-workers-per-env=N`, `--uc-wpe=N` | Override `workers_per_env` for every env, for this run only | Temporary experiments or CI override |
| `--uc-mt-plan[=LEVEL]` | Print the execution plan without starting anything | Preview workers, envs, and test assignment |
| `--uc-ju` | Start environment(s) and exit without running tests | CI warm-up, debugging |
| `--uc-fr` | Force restart of services | After changing compose/env config |
| `--uc-env=<name>` | Run only scenarios of one environment | Focused runs |
| `--uc-v[=LEVEL]` | Logging verbosity | Debugging |
| `--uc-<config>` | Select a named `ComposeConfig` (for example `--uc-dev`) | Multiple compose profiles |
| `--uc-external-services[=<name>]` | Use overridden external services | Local runs against shared infra |

`--uc-mt` can also be enabled from config:

```python
class UberComposeParallel(VedroUberComposeParallel):
    enabled = True
    multi_thread = True          # same as always passing --uc-mt
```

## `ComposeConfig` fields

| Field | Default | Meaning |
|---|---|---|
| `compose_files` | — | Compose files for the environment |
| `workers_per_env` | `None` | `{env_description: workers}`. Omitted or `{}` means `default_workers_per_env` for every env |
| `default_workers_per_env` | `1` | Workers for envs not listed in `workers_per_env` |
| `max_concurrent_envs` | `1` | Sequential runs: env groups allowed to stay alive at once. `1` = rotation, `>1` = envs may coexist. Parallel workers always namespace and keep envs |
| `overridden_services` | `None` | Services replaced by external ones |

## Current env API

The plugin fills a per-process context before every scenario. All getters are
static on `TheUberCompose`, so they work without creating the singleton:

```python
from uber_compose import TheUberCompose

TheUberCompose.current_env_id()          # "w1-a1b2" or "default_env_id"
TheUberCompose.current_env()             # Environment instance or None
TheUberCompose.current_service_env("api")
TheUberCompose.current_service_env_param("api", "DB_NAME")
TheUberCompose.current_worker_id()
TheUberCompose.current_workers_total()
TheUberCompose.is_current_worker_parallel()
TheUberCompose.current_replica_index()
TheUberCompose.current_replicas_total()
TheUberCompose.current_namespace()
TheUberCompose.current_worker_groups()
TheUberCompose.current_run_id()
TheUberCompose.current_run_depth()
TheUberCompose.is_child_project()
```

`current_run_depth()` is `0` for a normal run and increases for nested
`vedro run` projects launched from scenarios.

`current_env_id()` is a `ContextVar`: it is available in the scenario and in
async tasks of the same worker process, but not in arbitrary child processes or
threads.

## Parameterization placeholders

Resolved in service env parameters **and** `x-migration` commands:

- `[[env_id]]` — current environment id / namespace;
- `[[namespace]]` — namespace key (same as `env_id` today);
- `[[worker_id]]` — worker index (`0` for a single worker);
- `[[test_run_id]]` — run id;
- `[[<service>]]` — actual namespaced service name (`[[postgres]]` →
  `postgres-w1-a1b2`).

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

```yaml
services:
  api:
    x-migration:
      - after_start: sh -c 'echo "[[env_id]]:[[s1]]" >> /tmp/migration.log'
```

## Reporting details

Workers emit JSON events that the parent turns back into regular vedro events,
so standard reporters (rich, pycharm, json) work in parallel mode. The parent
reconstructs scenario results including:

- status, timings, skip reason;
- steps (names, statuses, timings);
- step errors (type/message, synthetic traceback);
- artifacts attached to scenarios and steps (`MemoryArtifact`, `FileArtifact`);
- captured output and extra details.

Workers are always started with output capture, so user `print()` output cannot
corrupt the machine-readable worker protocol; captured output is transferred to
the parent report.

## Failure handling

- A worker that exits before reporting its scenarios does not cancel the
  others: its scenarios are reported as failed with
  `Worker N exited with code X`.
- A spawn error is reported as `Worker N failed to start: ...`.
- `worker_timeout` kills a hung worker; its scenarios are reported as failed
  with `Worker N timed out`.
- On interrupt, the runner kills all spawned worker processes before exiting.

## Limitations

- `FileArtifact` assumes the file is reachable by the parent (shared filesystem
  for local runs).
- Shared singleton state is isolated only at the level the tests/configuration
  provide (database names, topic prefixes, etc.).
