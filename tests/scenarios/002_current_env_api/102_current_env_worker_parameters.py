import vedro

from uber_compose import Env
from uber_compose import Environment
from uber_compose import Service
from uber_compose import TheUberCompose
from uber_compose.helpers.current_env import CurrentEnvContext
from uber_compose.helpers.current_env import reset_current_env_id
from uber_compose.helpers.current_env import set_current_env_context


class Scenario(vedro.Scenario):
    subject = 'the uber compose exposes current env and worker parameters'

    async def given_active_parallel_worker_context(self):
        reset_current_env_id()
        vedro.defer(reset_current_env_id)
        self.environment = Environment(
            Service('db', env=Env({'DB_NAME': 'app_w1', 'PORT': '5432'})),
            description='env-a',
        )
        set_current_env_context(CurrentEnvContext(
            env_id='w1-a1b2',
            env=self.environment,
            worker_id=1,
            workers_total=3,
            replica_index=1,
            replicas_total=3,
            namespace='w1-a1b2',
            groups=('hash-a',),
            run_id='run-123',
            run_depth=1,
        ))

    async def when_current_env_api_is_read(self):
        client = TheUberCompose
        self.env_id = client.current_env_id()
        self.env = client.current_env()
        self.service_env = client.current_service_env('db')
        self.service_env_param = client.current_service_env_param('db', 'DB_NAME')
        self.missing_service_env_param = client.current_service_env_param('db', 'MISSING', 'fallback')
        self.unknown_service_env = client.current_service_env('unknown')
        self.worker_id = client.current_worker_id()
        self.workers_total = client.current_workers_total()
        self.is_parallel = client.is_current_worker_parallel()
        self.replica_index = client.current_replica_index()
        self.replicas_total = client.current_replicas_total()
        self.groups = client.current_worker_groups()
        self.namespace = client.current_namespace()
        self.run_id = client.current_run_id()
        self.run_depth = client.current_run_depth()
        self.is_child_project = client.is_child_project()

    async def then_it_should_return_current_env_id(self):
        assert self.env_id == 'w1-a1b2'

    async def and_it_should_return_current_env(self):
        assert self.env == self.environment

    async def and_it_should_return_service_env_params(self):
        assert self.service_env == {'DB_NAME': 'app_w1', 'PORT': '5432'}
        assert self.service_env_param == 'app_w1'
        assert self.missing_service_env_param == 'fallback'
        assert self.unknown_service_env is None

    async def and_it_should_return_worker_parameters(self):
        assert self.worker_id == 1
        assert self.workers_total == 3
        assert self.is_parallel is True
        assert self.replica_index == 1
        assert self.replicas_total == 3
        assert self.groups == ['hash-a']
        assert self.namespace == 'w1-a1b2'
        assert self.run_id == 'run-123'
        assert self.run_depth == 1
        assert self.is_child_project is True
