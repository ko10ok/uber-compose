from pathlib import Path
from typing import NamedTuple

from uber_compose.env_description.env_types import Environment
from uber_compose.env_description.env_types import OverridenService

DEFAULT_ENV_ID = 'default_env_id'


class ComposeConfig(NamedTuple):
    compose_files: str
    overridden_services: list[OverridenService] = None
    workers_per_env: dict[str | Environment, int] | None = None
    default_workers_per_env: int = 1
    max_concurrent_envs: int = 1


class EnvInstanceConfig(NamedTuple):
    env_source: Environment
    env_name: str
    env_id: str
    env_services_map: dict[str, str]
    env: Environment
    placeholders: dict[str, str] = None


class ComposeInstanceFiles(NamedTuple):
    env_config_instance: EnvInstanceConfig
    compose_files_source: str
    directory: Path
    compose_files: str
    inline_migrations: dict = None
    compose_config: dict = None
