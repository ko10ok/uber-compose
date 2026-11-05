from contextvars import ContextVar
from dataclasses import dataclass
from dataclasses import replace
from typing import Any

from uber_compose.core.sequence_run_types import DEFAULT_ENV_ID


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


def reset_current_env_id() -> None:
    _current_env.set(_default_context)


__all__ = (
    'CurrentEnvContext', 'get_current_env_context', 'get_current_env_id',
    'reset_current_env_id', 'set_current_env_context', 'set_current_env_id',
)
