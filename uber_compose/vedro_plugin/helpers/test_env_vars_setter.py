import os
from _warnings import warn

from uber_compose.env_description.env_types import Environment
from uber_compose.env_description.env_types import OverridenService


def setup_env_for_tests(env: Environment, overridden_services: list[OverridenService], run_id):
    updated_env = {}
    for service in env:
        for k, v in env[service].env.items():
            # if k in updated_env and updated_env[k] != v:
            #     warn(
            #         f'⚠️ env {k} tried to setup up multiple'
            #         f' times with different values: {updated_env[k]} vs {v}'
            #     )
            if isinstance(v, str):
                v = v.replace('[[test_run_id]]', run_id)
            updated_env[k] = v
            os.environ[k] = v

    if overridden_services is None:
        overridden_services = []
    for overriden_service in overridden_services:
        for env_fix in overriden_service.services_envs_fix:
            for k, v in env_fix.env.items():
                if isinstance(v, str):
                    v = v.replace('[[test_run_id]]', run_id)
                updated_env[k] = v
                os.environ[k] = v
