import hashlib
import string

PLACEHOLDER_ENV_ID = 'env_id'
PLACEHOLDER_WORKER_ID = 'worker_id'
PLACEHOLDER_NAMESPACE = 'namespace'
PLACEHOLDER_WORKER_ID_ALPHA_NUMERIC = 'worker_id_alpha_numeric'
PLACEHOLDER_NAMESPACE_ALPHA_NUMERIC = 'namespace_alpha_numeric'
PLACEHOLDER_WORKER_ID_ALPHA_NUMERIC_6 = 'worker_id_alpha_numeric_6'
PLACEHOLDER_NAMESPACE_ALPHA_NUMERIC_6 = 'namespace_alpha_numeric_6'
PLACEHOLDER_TEST_RUN_ID = 'test_run_id'

ALPHA_NUMERIC_6_LENGTH = 6

_ALPHA = string.ascii_lowercase
_ALPHA_NUMERIC = _ALPHA + string.digits


def make_alpha_numeric_identifier(value) -> str:
    identifier = ''.join(
        char if char.isascii() and char.isalnum() else ''
        for char in str(value)
    )
    if not identifier or not identifier[0].isascii() or not identifier[0].isalpha():
        identifier = f'k{identifier}'
    return identifier


def make_alpha_numeric_identifier_with_length(value, length: int) -> str:
    if length < 1:
        raise ValueError('Identifier length should be positive')

    digest = hashlib.sha1(str(value).encode()).hexdigest()
    number = int(digest, 16)
    chars = []
    for _ in range(length):
        number, remainder = divmod(number, len(_ALPHA_NUMERIC))
        chars.append(_ALPHA_NUMERIC[remainder])

    identifier = ''.join(reversed(chars))
    if not identifier[0].isalpha():
        first_index = int(digest[:2], 16) % len(_ALPHA)
        identifier = f'{_ALPHA[first_index]}{identifier[1:]}'

    return identifier


def build_parameterization_placeholders(
    env_id,
    services_map: dict[str, str] | None = None,
    run_id: str | None = None,
    worker_id: int | None = None,
    namespace: str | None = None,
) -> dict[str, str]:
    placeholders = dict(services_map or {})
    resolved_namespace = namespace if namespace is not None else env_id
    placeholders[PLACEHOLDER_ENV_ID] = str(env_id)
    placeholders[PLACEHOLDER_NAMESPACE] = str(resolved_namespace)
    placeholders[PLACEHOLDER_NAMESPACE_ALPHA_NUMERIC] = make_alpha_numeric_identifier(
        resolved_namespace
    )
    placeholders[PLACEHOLDER_NAMESPACE_ALPHA_NUMERIC_6] = make_alpha_numeric_identifier_with_length(
        resolved_namespace,
        ALPHA_NUMERIC_6_LENGTH,
    )
    if run_id is not None:
        placeholders[PLACEHOLDER_TEST_RUN_ID] = str(run_id)
    if worker_id is not None:
        worker_value = f'w{worker_id}'
        placeholders[PLACEHOLDER_WORKER_ID] = str(worker_id)
        placeholders[PLACEHOLDER_WORKER_ID_ALPHA_NUMERIC] = make_alpha_numeric_identifier(worker_value)
        placeholders[PLACEHOLDER_WORKER_ID_ALPHA_NUMERIC_6] = make_alpha_numeric_identifier_with_length(
            worker_value,
            ALPHA_NUMERIC_6_LENGTH,
        )
    return placeholders


def substitute_parameterization_placeholders(value, placeholders: dict[str, str]):
    if not isinstance(value, str):
        return value
    for name, replacement in placeholders.items():
        value = value.replace(f'[[{name}]]', str(replacement))
    return value


__all__ = (
    'ALPHA_NUMERIC_6_LENGTH', 'PLACEHOLDER_ENV_ID', 'PLACEHOLDER_NAMESPACE',
    'PLACEHOLDER_NAMESPACE_ALPHA_NUMERIC', 'PLACEHOLDER_NAMESPACE_ALPHA_NUMERIC_6',
    'PLACEHOLDER_TEST_RUN_ID', 'PLACEHOLDER_WORKER_ID', 'PLACEHOLDER_WORKER_ID_ALPHA_NUMERIC',
    'PLACEHOLDER_WORKER_ID_ALPHA_NUMERIC_6', 'build_parameterization_placeholders',
    'make_alpha_numeric_identifier', 'make_alpha_numeric_identifier_with_length',
    'substitute_parameterization_placeholders',
)
