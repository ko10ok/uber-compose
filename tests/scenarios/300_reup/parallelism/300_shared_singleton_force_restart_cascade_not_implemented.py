import vedro


@vedro.skip(reason=(
    'Not implemented: force_restart of an environment that shares a singleton with a '
    'parallel neighbour must cascade to dependent services instead of restarting the '
    'shared singleton in place.'
))
class Scenario(vedro.Scenario):
    subject = 'force restart shared singleton cascades to dependent environments'

    def when_user_force_restarts_one_of_the_parallel_envs(self):
        raise NotImplementedError

    def then_shared_singleton_and_dependants_should_be_restarted_cascaded(self):
        raise NotImplementedError
