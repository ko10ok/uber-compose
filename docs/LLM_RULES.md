LLM rules for this repository. If your task concerns a specific point below,
jump to and read that section before acting.

## Table of contents

1. [Running e2e tests](#running-e2e-tests)
2. [After developing a feature and its tests](#after-developing-a-feature-and-its-tests)

## Running e2e tests

Test runs in test directory.

To run tests: make e2e-run args='scenarios/'

To run tests with verbose output: make e2e-run args='scenarios/ -vvv'

To run tests with environment rebuild or to up environment (only if application code changed): make e2e-run args='scenarios/ -vvv' -B

## After developing a feature and its tests

Before considering a feature/task done, from the repo root (not from `tests/`)
run, after the e2e tests pass:

1. `make venv` — creates/updates the local `.venv-lint` dev venv (isort, flake8)
   used by the targets below. Not needed to call directly, it's a dependency
   of `e2e-fix-imports` and `lint`, but can be run on its own too.
2. `make e2e-fix-imports` — auto-fixes import order (isort) in `uber_compose`
   and `tests`.
3. `make lint` — re-checks import order and runs flake8; must pass with no
   errors.

