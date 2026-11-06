from helpers.env_vars import patch_env
import vedro

from uber_compose import get_namespace_map
from uber_compose import get_worker_groups
from uber_compose import get_worker_id
from uber_compose import get_workers_total
from uber_compose import is_parallel_worker


class Scenario(vedro.Scenario):
    subject = 'worker api reads parallel env variables set by the orchestrator'

    async def given_parallel_env_variables(self):
        patch_env({
            'UC_WORKER_ID': '2',
            'UC_WORKERS_TOTAL': '4',
            'UC_WORKER_GROUPS': 'hash-a, hash-b',
            'UC_NAMESPACE_MAP': '{"hash-a": "w2-a1b2", "hash-b": "w2-c3d4"}',
        })

    async def then_it_should_return_worker_id(self):
        assert get_worker_id() == 2

    async def and_it_should_return_workers_total(self):
        assert get_workers_total() == 4

    async def and_it_should_be_a_parallel_worker(self):
        assert is_parallel_worker() is True

    async def and_it_should_return_worker_groups(self):
        assert get_worker_groups() == ['hash-a', 'hash-b']

    async def and_it_should_return_namespace_map(self):
        assert get_namespace_map() == {'hash-a': 'w2-a1b2', 'hash-b': 'w2-c3d4'}
