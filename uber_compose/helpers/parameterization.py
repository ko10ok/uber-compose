PLACEHOLDER_ENV_ID = 'env_id'
PLACEHOLDER_WORKER_ID = 'worker_id'
PLACEHOLDER_NAMESPACE = 'namespace'
PLACEHOLDER_TEST_RUN_ID = 'test_run_id'


def build_parameterization_placeholders(
    env_id,
    services_map: dict[str, str] | None = None,
    run_id: str | None = None,
    worker_id: int | None = None,
    namespace: str | None = None,
) -> dict[str, str]:
    placeholders = dict(services_map or {})
    placeholders[PLACEHOLDER_ENV_ID] = str(env_id)
    placeholders[PLACEHOLDER_NAMESPACE] = str(namespace if namespace is not None else env_id)
    if run_id is not None:
        placeholders[PLACEHOLDER_TEST_RUN_ID] = str(run_id)
    if worker_id is not None:
        placeholders[PLACEHOLDER_WORKER_ID] = str(worker_id)
    return placeholders


def substitute_parameterization_placeholders(value, placeholders: dict[str, str]):
    if not isinstance(value, str):
        return value
    for name, replacement in placeholders.items():
        value = value.replace(f'[[{name}]]', str(replacement))
    return value


__all__ = (
    'PLACEHOLDER_ENV_ID', 'PLACEHOLDER_NAMESPACE', 'PLACEHOLDER_TEST_RUN_ID', 'PLACEHOLDER_WORKER_ID',
    'build_parameterization_placeholders', 'substitute_parameterization_placeholders',
)
