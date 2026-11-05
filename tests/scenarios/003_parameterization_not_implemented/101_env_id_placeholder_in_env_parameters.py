import vedro


@vedro.skip(reason='Not implemented: [[env_id]] substitution in service env parameters')
class Scenario(vedro.Scenario):
    subject = 'use env_id placeholder in service env parameters'
