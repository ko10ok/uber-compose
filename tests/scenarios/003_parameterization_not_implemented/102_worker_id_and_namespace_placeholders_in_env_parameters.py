import vedro


@vedro.skip(reason='Not implemented: [[worker_id]] and [[namespace]] placeholders in service env parameters')
class Scenario(vedro.Scenario):
    subject = 'use worker_id and namespace placeholders in service env parameters'
