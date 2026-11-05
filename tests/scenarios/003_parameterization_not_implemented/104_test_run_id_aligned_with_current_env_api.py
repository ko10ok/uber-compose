import vedro


@vedro.skip(reason=(
    'Not implemented: [[test_run_id]] is not exposed through the current env api '
    'and is not aligned with current env/run metadata'
))
class Scenario(vedro.Scenario):
    subject = 'use test_run_id placeholder aligned with the current env api'
