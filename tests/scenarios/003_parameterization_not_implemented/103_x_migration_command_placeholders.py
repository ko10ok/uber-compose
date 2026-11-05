import vedro


@vedro.skip(reason='Not implemented: templating of x-migration commands with [[service]] and [[env_id]]')
class Scenario(vedro.Scenario):
    subject = 'use service names and env_id in x-migration commands'
