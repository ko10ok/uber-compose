# Plan and runtime consistency

Status: proposed

This document describes how to make the Uber Compose execution plan and the
actual run converge on a single source of truth.

The target state is:

```text
build_run_plan(...)  -> RunPlan
    ├── render_plan(plan)      # --uc-mt-plan
    └── apply_run_plan(plan)   # actual execution
```

The planner must not be a separate approximation of the run. The actual run
must not rebuild a different plan from the same inputs.

## Goals

- Start with point validation of actual runtime facts against the current plan.
- Keep validation non-invasive first.
- Move to a single shared `RunPlan` used by both planning and execution.
- Keep sequential and parallel modes consistent.
- Make mismatches visible as warnings or errors.
- Preserve current behavior by default.

## Non-goals

- Replacing Docker or Compose state reconciliation.
- Predicting Docker failures, healthcheck failures, or retries.
- Making `--uc-mt-plan` execute anything.
- Guaranteeing that an already-running environment will always be reused.

## Current state

Implemented:

- `--uc-mt-plan` with levels `0`, `1`, `2`;
- plan data model and renderer in `uber_compose/parallel_plugin/planner.py`;
- plan builder using the same grouping and replica primitives as the parallel
  plugin;
- tests for sequential and parallel plan output;
- tests proving that plan mode does not start containers.

Known inconsistency risks:

1. `VedroUberComposeParallelPlugin._build_replica_plan()` and
   `build_run_plan()` both derive a plan from the scheduler.
2. Sequential execution does not consume `RunPlan` at all.
3. `--uc-mt-plan` can know planned env IDs and worker assignments, but the
   actual runner does not explicitly compare them.
4. Worker processes receive assignments via environment variables, but there is
   no plan check inside the worker.
5. Actual env reuse and external overrides can change effective behavior after
   the plan was rendered.

## Phase 0: point validation of current facts

Do this first. It should not change execution behavior.

Add a read-only validation layer:

```text
--uc-plan-check=off     # default
--uc-plan-check=warn    # print mismatches, continue
--uc-plan-check=strict  # fail on mismatch
```

### Validation points

#### 1. After scenario discovery

Compare:

- env groups in the plan vs env groups discovered from scenarios;
- scenario paths assigned to each env;
- worker count per env;
- `workers_per_env` and `default_workers_per_env` decisions;
- ignored scenarios from `--uc-env`.

#### 2. Before spawning workers

Compare:

- `plan.workers_total` vs workers about to be spawned;
- assignment groups;
- namespace map;
- replica index / replicas total;
- scenario count per worker.

#### 3. Inside each worker

Compare environment values against the planned assignment:

- `UC_WORKER_ID`;
- `UC_WORKERS_TOTAL`;
- `UC_WORKER_GROUPS`;
- `UC_NAMESPACE_MAP`;
- `UC_WORKER_REPLICA_INDEX`;
- `UC_ENV_REPLICAS_TOTAL`;
- current env context after UC plugin setup.

#### 4. After environment preparation

Compare:

- actual env ID vs planned namespace;
- actual service names vs planned services;
- singleton/external/off service decisions;
- overrides applied;
- environment description.

#### 5. After the run

Compare:

- actual executed scenarios per worker vs planned;
- missing or duplicated scenarios;
- skipped-by-plan vs skipped-by-runtime.

### Validation result

```python
@dataclass(frozen=True)
class PlanMismatch:
    stage: str
    expected: object
    actual: object
    message: str


@dataclass(frozen=True)
class PlanCheckResult:
    mismatches: tuple[PlanMismatch, ...]

    @property
    def ok(self) -> bool:
        return not self.mismatches
```

### Warnings

In `warn` mode, log:

```text
[UberCompose] plan mismatch at worker-start
  expected: 3 workers for env-a
  actual:   2 workers
  hint: workers are capped by the number of scenarios
```

In `strict` mode, exit with a clear error.

### What not to validate yet

Do not fail on:

- existing environment reuse;
- retries;
- healthcheck timing;
- Docker network exhaustion;
- external service state.

These are runtime conditions, not plan errors.

## Phase 1: extract a shared plan builder

The current planner and parallel plugin must call the same builder.

Proposed API:

```python
async def build_run_plan(
    scheduler,
    *,
    compose_config: str,
    compose_files: str | None,
    default_env: Environment | None,
    workers_per_env: dict | None,
    default_workers_per_env: int,
    max_concurrent_envs: int,
    uc_mt_enabled: bool,
    workers_per_env_override: int | None = None,
) -> RunPlan:
    ...
```

Then:

- `--uc-mt-plan` uses `build_run_plan()` and `render_plan()`;
- `VedroUberComposeParallelPlugin` uses an `ExecutionPlan` extracted from the
  same `RunPlan`;
- sequential mode starts using `RunPlan` for env order and lifecycle.

### Target model

```python
@dataclass(frozen=True)
class RunPlan:
    compose_config: str
    compose_files: str | None
    parallel: bool
    environments: tuple[PlanEnvironment, ...]
    execution_plan: ExecutionPlan | None
    max_concurrent_envs: int
    default_workers_per_env: int
    uc_mt_enabled: bool
    ignored: tuple[str, ...]
```

`PlanEnvironment` should carry:

- env description;
- services and modes;
- env templates;
- test paths;
- replicas and namespaces;
- plan source: config, override, default env, auto-scanned env.

## Phase 2: actual run consumes the plan

After the shared builder exists, the actual run should not recompute:

- worker count;
- assignments;
- namespace map;
- scenario distribution;
- env order for sequential mode.

Instead:

```python
plan = await build_run_plan(...)
if plan_mode:
    print(render_plan(plan, level=plan_level))
    return
await apply_run_plan(plan)
```

### Parallel mode

`apply_run_plan()`:

- starts planned env replicas;
- spawns `plan.execution_plan.workers_total` workers;
- passes each worker the planned assignment;
- optionally checks the worker environment against the assignment.

### Sequential mode

`apply_run_plan()`:

- uses planned env order;
- uses planned test grouping only for reporting/validation;
- keeps current lifecycle behavior:
  - `max_concurrent_envs=1` -> rotation;
  - `max_concurrent_envs>1` -> coexistence.

## Phase 3: plan source and fingerprints

Add plan metadata for debugging:

```python
@dataclass(frozen=True)
class PlanSource:
    compose_config: str
    workers_per_env: dict[str, int] | None
    workers_per_env_override: int | None
    default_workers_per_env: int
    max_concurrent_envs: int
    uc_mt_enabled: bool
    default_env_source: str  # explicit | auto_scanned
    ignored_settings: tuple[str, ...]
```

Add a stable plan fingerprint:

```python
plan_fingerprint = sha1(serialize_plan_identity(plan))
```

Use it:

- in logs;
- in plan output at level 2;
- in worker environment as `UC_PLAN_FINGERPRINT`;
- in validation messages.

This makes it possible to see whether a worker is running the same plan as the
orchestrator.

## Phase 4: strict consistency mode

Once phases 0-3 are stable:

- make `--uc-plan-check=warn` the default for debug verbosity;
- document `--uc-plan-check=strict` for CI;
- add CI coverage for a few representative cases:
  - one env, multiple workers;
  - multiple envs;
  - singleton;
  - external overrides;
  - `--uc-wpe` override;
  - sequential rotation.

## Invariants

The following should be true in all modes:

| Invariant | Where checked |
|---|---|
| Every planned worker has exactly one assignment | before spawn |
| Every worker assignment has a namespace | before spawn |
| Worker env matches assignment | inside worker |
| Actual env ID matches planned namespace | after env up |
| Actual services match planned service set | after env up |
| No scenario is executed by two workers | after run |
| No planned scenario is missing without reason | after run |
| Sequential env order matches plan | during run |
| `max_concurrent_envs` behavior matches lifecycle | during run |

## Tests

### Phase 0 tests

- Plan has 2 workers, actual starts 2 -> no warning.
- Plan has 2 workers, actual starts 1 -> warning.
- Worker gets wrong `UC_WORKER_ID` -> warning.
- Worker namespace map differs -> warning.
- Actual env ID differs from plan -> warning.
- `strict` mode turns the same mismatch into a failure.

### Phase 1 tests

- `--uc-mt-plan` and actual parallel run produce the same `ExecutionPlan`.
- Sequential plan and sequential run use the same env order.
- `--uc-wpe` appears in both plan and actual worker count.
- `--uc-env` filter appears in both plan and actual scenario set.

### Phase 2 tests

- Worker spawn uses `plan.execution_plan` directly.
- Sequential run uses `plan.environments` order.
- No plan recalculation happens in the runner.

### Phase 3 tests

- Same plan produces the same fingerprint.
- Worker receives the orchestrator fingerprint.
- Fingerprint mismatch is reported.

## Migration order

1. Add `PlanMismatch` / `PlanCheckResult`.
2. Add `--uc-plan-check=warn|strict`.
3. Add validation at scenario discovery and worker start.
4. Add worker-side validation.
5. Add env-preparation validation.
6. Extract `build_run_plan()` and switch parallel plugin to it.
7. Switch sequential path to `RunPlan`.
8. Remove duplicate plan-building code.
9. Add plan fingerprint.
10. Make the plan check part of CI for selected scenarios.

## Risks

| Risk | Mitigation |
|---|---|
| Plan and runtime intentionally differ because of env reuse | Validate only deterministic invariants first |
| Existing tests depend on duplicated planning behavior | Keep Phase 0 read-only and opt-in |
| Sequential migration changes lifecycle | Migrate in a separate phase with dedicated tests |
| Warnings become noisy | Default `off`, enable `warn` for debug |
| Plan fingerprint changes too often | Fingerprint only stable identity fields |

## Open questions

1. Should `--uc-plan-check` default to `off` or `warn`?
2. Should `strict` fail before spawning workers or after?
3. Should worker-side mismatch kill the worker or just log?
4. Should plan fingerprint include service env values or only env identity?
5. Should sequential `RunPlan` include exact scenario order or only env order?

## Definition of done

- A shared `RunPlan` builds both the rendered plan and the actual run.
- Sequential and parallel modes use the same plan builder.
- `--uc-mt-plan` and actual execution agree on workers, namespaces, envs, and
  scenario distribution.
- Mismatches are reported with a clear stage and hint.
- `--uc-plan-check=strict` can be used in CI.
- Tests cover plan-vs-actual consistency for the main parallelism cases.
