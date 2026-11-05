import vedro


@vedro.skip(reason=(
    'GitLab reporter plugin is not installed in the e2e environment. '
    'Enable it to validate that parallel event relay produces correct GitLab output.'
))
class Scenario(vedro.Scenario):
    subject = 'run vedro with parallel workers and gitlab reporter'
