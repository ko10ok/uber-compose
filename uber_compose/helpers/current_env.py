from contextvars import ContextVar

from uber_compose.core.sequence_run_types import DEFAULT_ENV_ID

_current_env_id: ContextVar[str] = ContextVar(
    'uber_compose_current_env_id',
    default=DEFAULT_ENV_ID,
)


def set_current_env_id(env_id: str) -> None:
    _current_env_id.set(env_id)


def get_current_env_id() -> str:
    return _current_env_id.get()


def reset_current_env_id() -> None:
    _current_env_id.set(DEFAULT_ENV_ID)
