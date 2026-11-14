import vedro

from uber_compose import TheUberCompose
from uber_compose.helpers.current_env import reset_current_env_id


class Scenario(vedro.Scenario):
    subject = 'the uber compose exposes default current env context without an active environment'

    async def given_reset_current_env(self):
        reset_current_env_id()
        vedro.defer(reset_current_env_id)

    async def when_current_env_api_is_read(self):
        client = TheUberCompose
        self.env_id = client.current_env_id()
        self.env = client.current_env()
        self.service_env = client.current_service_env('s1')
        self.worker_id = client.current_worker_id()
        self.workers_total = client.current_workers_total()
        self.is_parallel = client.is_current_worker_parallel()
        self.replica_index = client.current_replica_index()
        self.replicas_total = client.current_replicas_total()
        self.groups = client.current_worker_groups()
        self.run_id = client.current_run_id()
        self.namespace = client.current_namespace()
        self.run_depth = client.current_run_depth()
        self.is_child_project = client.is_child_project()

    async def then_it_should_return_default_env_id(self):
        assert self.env_id == 'default_env_id'

    async def and_it_should_have_no_current_env_params(self):
        assert self.env is None
        assert self.service_env is None

    async def and_it_should_return_default_worker_parameters(self):
        assert self.worker_id == 0
        assert self.workers_total == 1
        assert self.is_parallel is False
        assert self.replica_index is None
        assert self.replicas_total is None
        assert self.groups == []
        assert self.run_id is None
        assert self.namespace == 'default_env_id'
        assert self.run_depth == 0
        assert self.is_child_project is False
