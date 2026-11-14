import vedro

from uber_compose import Environment
from uber_compose import Service
from uber_compose import TheUberCompose
from uber_compose.helpers.current_env import CurrentEnvContext
from uber_compose.helpers.current_env import reset_current_env_id
from uber_compose.helpers.current_env import set_current_env_context
from uber_compose.helpers.current_env import set_current_env_id


class Scenario(vedro.Scenario):
    subject = 'changing current env id preserves the rest of the current env context'

    async def given_active_context(self):
        reset_current_env_id()
        vedro.defer(reset_current_env_id)
        set_current_env_context(CurrentEnvContext(
            env_id='w0-old',
            env=Environment(Service('s1'), description='env-a'),
            worker_id=0,
            workers_total=2,
            run_id='run-1',
        ))

    async def when_current_env_id_is_changed_and_api_is_read(self):
        set_current_env_id('w0-new')
        client = TheUberCompose
        self.env_id = client.current_env_id()
        self.service_names = set(client.current_env().get_services().keys())
        self.worker_id = client.current_worker_id()
        self.workers_total = client.current_workers_total()
        self.run_id = client.current_run_id()

    async def then_it_should_update_only_env_id(self):
        assert self.env_id == 'w0-new'
        assert self.service_names == {'s1'}
        assert self.worker_id == 0
        assert self.workers_total == 2
        assert self.run_id == 'run-1'
