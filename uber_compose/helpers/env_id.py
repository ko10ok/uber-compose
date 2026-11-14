import hashlib

from uber_compose.helpers.bytes_pickle import base64_pickled


def get_template_hash(config_template, length: int = 4) -> str:
    payload = base64_pickled(config_template)
    return hashlib.sha1(payload.encode()).hexdigest()[:length]


def get_stable_env_id(config_template, index: int) -> str:
    return f'w{index}-{get_template_hash(config_template)}'


def stable_index(key: str, total: int) -> int:
    total = max(total, 1)
    digest = hashlib.sha1(str(key).encode()).hexdigest()
    return int(digest, 16) % total


__all__ = ("get_stable_env_id", "get_template_hash", "stable_index",)
