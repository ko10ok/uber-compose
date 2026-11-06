from contextvars import ContextVar
from dataclasses import dataclass
from dataclasses import replace
import os
from typing import Any

from uber_compose.core.sequence_run_types import DEFAULT_ENV_ID

RUN_DEPTH_ENV = 'UC_RUN_DEPTH'


@dataclass(frozen=True)
class CurrentEnvContext:
    env_id: str = DEFAULT_ENV_ID
    env: Any = None
    worker_id: int = 0
    workers_total: int = 1
    replica_index: int | None = None
    replicas_total: int | None = None
    namespace: str | None = None
    groups: tuple[str, ...] = ()
    run_id: str | None = None
    run_depth: int = 0


_default_context = CurrentEnvContext()

_current_env: ContextVar[CurrentEnvContext] = ContextVar(
    'uber_compose_current_env',
    default=_default_context,
)


def set_current_env_context(context: CurrentEnvContext) -> None:
    _current_env.set(context)


def get_current_env_context() -> CurrentEnvContext:
    return _current_env.get()


def set_current_env_id(env_id: str) -> None:
    _current_env.set(replace(_current_env.get(), env_id=env_id))


def get_current_env_id() -> str:
    return _current_env.get().env_id


def _env_run_depth() -> int:
    raw = os.environ.get(RUN_DEPTH_ENV)
    if raw is None or raw == '':
        return 0
    try:
        return max(int(raw), 0)
    except (TypeError, ValueError):
        return 0


def get_run_depth() -> int:
    return max(get_current_env_context().run_depth, _env_run_depth())


def set_run_depth(depth: int) -> None:
    os.environ[RUN_DEPTH_ENV] = str(max(int(depth), 0))


def increment_run_depth() -> int:
    depth = get_run_depth() + 1
    set_run_depth(depth)
    return depth


def is_child_project() -> bool:
    return get_run_depth() > 0


def reset_current_env_id() -> None:
    _current_env.set(_default_context)


__all__ = (
    'CurrentEnvContext', 'RUN_DEPTH_ENV', 'get_current_env_context',
    'get_current_env_id', 'get_run_depth', 'increment_run_depth',
    'is_child_project', 'reset_current_env_id', 'set_current_env_context',
    'set_current_env_id', 'set_run_depth',
)
