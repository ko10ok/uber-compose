import json
import os

from uber_compose.helpers.workers_per_env import normalize_workers_per_env
from uber_compose.parallel_plugin.types import ExecutionPlan

WORKER_ID_ENV = 'UC_WORKER_ID'
WORKERS_TOTAL_ENV = 'UC_WORKERS_TOTAL'
WORKER_GROUPS_ENV = 'UC_WORKER_GROUPS'
NAMESPACE_MAP_ENV = 'UC_NAMESPACE_MAP'
WORKER_REPLICA_INDEX_ENV = 'UC_WORKER_REPLICA_INDEX'
ENV_REPLICAS_TOTAL_ENV = 'UC_ENV_REPLICAS_TOTAL'

DEFAULT_WORKER_ID = 0
DEFAULT_WORKERS_TOTAL = 1

_execution_plan: ExecutionPlan | None = None
_workers_per_env: tuple[dict[str, int], int] | None = None
_default_workers_per_env: int = 1
_workers_per_env_override: int | None = None


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


def get_worker_replica_index() -> int | None:
    raw = os.environ.get(WORKER_REPLICA_INDEX_ENV)
    if raw is None or raw == '':
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def get_env_replicas_total() -> int | None:
    raw = os.environ.get(ENV_REPLICAS_TOTAL_ENV)
    if raw is None or raw == '':
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


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


def set_workers_per_env(counts: dict[str, int] | None, default: int = 1) -> None:
    global _workers_per_env, _default_workers_per_env
    _default_workers_per_env = max(int(default), 1)
    if counts is None:
        _workers_per_env = None
    else:
        _workers_per_env = (normalize_workers_per_env(counts), _default_workers_per_env)


def get_workers_per_env() -> tuple[dict[str, int], int] | None:
    return _workers_per_env


def get_default_workers_per_env() -> int:
    return _default_workers_per_env


def set_workers_per_env_override(value: int | None) -> None:
    global _workers_per_env_override
    _workers_per_env_override = None if value is None else max(int(value), 1)


def get_workers_per_env_override() -> int | None:
    return _workers_per_env_override


def reset_workers_per_env() -> None:
    set_workers_per_env(None)
    set_workers_per_env_override(None)


__all__ = (
    'DEFAULT_WORKER_ID', 'DEFAULT_WORKERS_TOTAL', 'ENV_REPLICAS_TOTAL_ENV',
    'NAMESPACE_MAP_ENV', 'WORKER_GROUPS_ENV', 'WORKER_ID_ENV', 'WORKER_REPLICA_INDEX_ENV', 'WORKERS_TOTAL_ENV',
    'get_default_workers_per_env', 'get_env_replicas_total', 'get_execution_plan',
    'get_namespace_map', 'get_workers_per_env', 'get_workers_per_env_override',
    'get_worker_groups', 'get_worker_id', 'get_worker_replica_index', 'get_workers_total',
    'is_parallel_worker', 'is_parallel_worker_process', 'reset_execution_plan',
    'reset_workers_per_env', 'set_execution_plan', 'set_workers_per_env',
    'set_workers_per_env_override',
)
