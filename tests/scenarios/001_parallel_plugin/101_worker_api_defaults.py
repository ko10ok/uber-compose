from helpers.env_vars import patch_env
import vedro

from uber_compose import get_namespace_map
from uber_compose import get_worker_groups
from uber_compose import get_worker_id
from uber_compose import get_workers_total
from uber_compose import is_parallel_worker


class Scenario(vedro.Scenario):
    subject = 'worker api returns safe defaults without parallel env variables'

    async def given_no_parallel_env_variables(self):
        patch_env({
            'UC_WORKER_ID': None,
            'UC_WORKERS_TOTAL': None,
            'UC_WORKER_GROUPS': None,
            'UC_NAMESPACE_MAP': None,
        })

    async def then_worker_id_should_be_zero(self):
        assert get_worker_id() == 0

    async def and_workers_total_should_be_one(self):
        assert get_workers_total() == 1

    async def and_it_should_not_be_a_parallel_worker(self):
        assert is_parallel_worker() is False

    async def and_worker_groups_should_be_none(self):
        assert get_worker_groups() is None

    async def and_namespace_map_should_be_empty(self):
        assert get_namespace_map() == {}
