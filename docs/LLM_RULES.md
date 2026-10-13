LLM rules for this repository. If your task concerns a specific point below,
jump to and read that section before acting.

## Table of contents

1. [Running e2e tests](#running-e2e-tests)
2. [After developing a feature and its tests](#after-developing-a-feature-and-its-tests)
3. [Setting up a local venv for isort/flake8 (fix-imports / lint)](#setting-up-a-local-venv-for-isortflake8-fix-imports--lint)

## Running e2e tests

Test runs in test directory.

To run tests: make e2e-run args='scenarios/'

To run tests with verbose output: make e2e-run args='scenarios/ -vvv'

To run tests with environment rebuild or to up environment (only if application code changed): make e2e-run args='scenarios/ -vvv' -B

## After developing a feature and its tests

Before considering a feature/task done, from the repo root run:

1. `make e2e-fix-imports` — auto-fixes import order (isort) in `uber_compose` and `tests`.
2. `make lint` — re-checks import order and runs flake8; must pass with no errors.

These two commands must be run from the repo root (not from `tests/`), after the
e2e tests pass.

## Setting up a local venv for isort/flake8 (fix-imports / lint)

System `python3` on this machine is externally managed (PEP 668), so
`pip3 install -r requirements-dev.txt` directly fails. Create and use a local
venv once per machine:

```
python3 -m venv .venv-lint
.venv-lint/bin/pip install --upgrade pip
.venv-lint/bin/pip install -r requirements-dev.txt -r requirements.txt
```

Then run the checks through that venv's interpreter instead of the Makefile's
`pip3`/`python3` (which assume a non-managed environment, as is the case in CI):

```
.venv-lint/bin/python3 -m isort uber_compose tests
.venv-lint/bin/python3 -m flake8 uber_compose tests
```

`.venv-lint/` is a local tool only and must not be committed.

