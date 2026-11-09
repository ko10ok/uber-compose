# Feature Request: Environment Locks

Status: proposed. Implementation is postponed.

## Summary

Add optional environment reservation so concurrent test runs do not use the same
already-running environment. A run that cannot reserve a matching environment must fail
fast instead of silently sharing it with another run.

## Problem

When several environments are already running, a run without parallel execution can pick
the same environment as another concurrently started run. Both runs then execute tests
against the same containers, which causes non-deterministic failures and makes results
hard to reproduce.

## User story

As a test runner user, I want each non-parallel test run to reserve one free matching
environment for the whole run, so two terminals or CI jobs cannot accidentally test
against the same environment at the same time.

## Configuration

- Locking is optional and disabled by default.
- Locking is enabled by an Uber Compose config flag only.
- No CLI flag is required to enable locking.
- Suggested config shape: `VedroUberCompose(env_locks=True, ...)`. Final flag name is
  still open.

## Lock scope and selection

- A lock is bound to a single `env_id`.
- The lock is held for the whole `vedro run`, not for an individual scenario.
- Only matching environments are considered: same environment template and compose files.
- Busy matching environments are skipped; the next matching free environment is used.
- Extra environments are never started just to satisfy the lock.
- If no matching environment exists, behavior is unchanged: the default environment is
  started and locked.
- If matching environments exist but all are locked, the run fails fast with a clear
  "all environments are busy" message.

## Lock files

- Location: `<PROJECT_ROOT_DIRECTORY>/.uc-locks/`.
- Name: `<env_id>.envlock`.
- Extension is deliberately `.envlock` so lock files are easy to ignore in git.
- The file contains at least the owner PID and process start time.
- Acquisition is atomic (`O_CREAT | O_EXCL` or equivalent).
- Process liveness is checked by PID and start time to avoid treating a reused PID as a
  live lock owner.
- Stale locks are removed automatically when the owner process is gone.

## Release and cleanup

- The lock is released after a successful run, a failed run, and on
  `KeyboardInterrupt` / `SIGINT`.
- `--uc-unlock` removes all `*.envlock` files and continues the current run.
- The command reports how many lock files were removed.

## Acceptance criteria

- With locking disabled, current behavior is unchanged.
- Two concurrent non-parallel runs with matching environments reserve different
  environments.
- A run that finds all matching environments locked fails with a clear
  "all environments are busy" message.
- A run with no matching environment starts and locks the default environment.
- Locks are released on success, failure, and interruption.
- Stale locks do not block future runs.
- `--uc-unlock` clears all lock files.
- Lock files are easy to ignore in git by extension.
- The implementation works on both direct `UberCompose.up()` usage and the vedro plugin
  path, or explicitly documents which path is covered.

## Open questions

- Lock mode is not finalized: earlier requirements mention non-parallel
  `parallelism=1`, while a later variant mentions `--uc-mt`.
- For `--uc-mt`, lock ownership is undecided:
  - parent process acquires locks before starting planned environments, or
  - each worker acquires the lock for its assigned `env_id`.
- If a planned `env_id` is busy under `--uc-mt`, the planner either:
  - fails fast, because the plan is deterministic, or
  - remaps the worker to the next free environment.
- Cleanup of worker locks on parallel-run interruption must be assigned to either the
  parent process or the workers.

## Out of scope

- Lock implementation.
- Lock tests.
- Locking for parallel or worker execution until the open questions are resolved.
- Cascading restart of services that depend on a shared singleton when
  `force_restart` is requested.
