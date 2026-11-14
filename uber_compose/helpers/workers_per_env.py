from uber_compose.env_description.env_types import Environment


def workers_per_env_key(key) -> str:
    if isinstance(key, Environment):
        return key.description
    return str(key)


def normalize_workers_per_env(values) -> dict[str, int] | None:
    if values is None:
        return None
    return {workers_per_env_key(key): int(count) for key, count in values.items()}


__all__ = ("normalize_workers_per_env", "workers_per_env_key",)
