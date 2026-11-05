import json
import os

from uber_compose.parallel_plugin.types import ExecutionPlan

WORKER_ID_ENV = 'UC_WORKER_ID'
WORKERS_TOTAL_ENV = 'UC_WORKERS_TOTAL'
WORKER_GROUPS_ENV = 'UC_WORKER_GROUPS'
NAMESPACE_MAP_ENV = 'UC_NAMESPACE_MAP'

DEFAULT_WORKER_ID = 0
DEFAULT_WORKERS_TOTAL = 1

_execution_plan: ExecutionPlan | None = None


def _read_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == '':
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def get_worker_id() -> int:
    return max(_read_int(WORKER_ID_ENV, DEFAULT_WORKER_ID), 0)


def get_workers_total() -> int:
    return max(_read_int(WORKERS_TOTAL_ENV, DEFAULT_WORKERS_TOTAL), 1)


def is_parallel_worker() -> bool:
    return get_workers_total() > 1


def is_parallel_worker_process() -> bool:
    return bool(os.environ.get(WORKER_ID_ENV))


def get_worker_groups() -> list[str] | None:
    raw = os.environ.get(WORKER_GROUPS_ENV)
    if not raw:
        return None
    groups = [part.strip() for part in raw.split(',')]
    return [group for group in groups if group]


def get_namespace_map() -> dict[str, str]:
    raw = os.environ.get(NAMESPACE_MAP_ENV)
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    if not isinstance(value, dict):
        return {}
    return {str(key): str(env_id) for key, env_id in value.items()}


def set_execution_plan(plan: ExecutionPlan | None) -> None:
    global _execution_plan
    _execution_plan = plan


def get_execution_plan() -> ExecutionPlan | None:
    return _execution_plan


def reset_execution_plan() -> None:
    set_execution_plan(None)


__all__ = (
    'DEFAULT_WORKER_ID', 'DEFAULT_WORKERS_TOTAL',
    'NAMESPACE_MAP_ENV', 'WORKER_GROUPS_ENV', 'WORKER_ID_ENV', 'WORKERS_TOTAL_ENV',
    'get_execution_plan', 'get_namespace_map', 'get_worker_groups', 'get_worker_id', 'get_workers_total',
    'is_parallel_worker', 'is_parallel_worker_process', 'reset_execution_plan', 'set_execution_plan',
)
