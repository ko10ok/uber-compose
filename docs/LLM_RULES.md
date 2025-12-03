Test runs in test directory.

To run tests: make e2e-run args='scenarios/'

To run tests with verbose output: make e2e-run args='scenarios/ -vvv'

To run tests with environment rebuild or to up environment (only if application code changed): make e2e-run args='scenarios/ -vvv' -B
