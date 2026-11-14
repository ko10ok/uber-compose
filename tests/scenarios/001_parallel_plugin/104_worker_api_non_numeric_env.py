from helpers.env_vars import patch_env
import vedro

from uber_compose import get_worker_id
from uber_compose import get_workers_total


class Scenario(vedro.Scenario):
    subject = 'worker api falls back to defaults on non-numeric worker env variables'

    async def given_non_numeric_worker_env_variables(self):
        patch_env({
            'UC_WORKER_ID': 'abc',
            'UC_WORKERS_TOTAL': 'many',
        })

    async def then_it_should_return_default_worker_id(self):
        assert get_worker_id() == 0

    async def and_it_should_return_default_workers_total(self):
        assert get_workers_total() == 1
