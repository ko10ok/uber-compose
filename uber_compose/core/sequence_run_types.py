from pathlib import Path
from typing import NamedTuple
from typing import Union

from uber_compose.env_description.env_types import OverridenService
from uber_compose.env_description.env_types import Environment

DEFAULT_ENV_ID = 'default_env_id'


class ComposeConfig(NamedTuple):
    compose_files: str
    overridden_services: list[OverridenService] = None
    parallel_env_limit: Union[int] = 1


class EnvInstanceConfig(NamedTuple):
    env_source: Environment
    env_name: str
    env_id: str
    env_services_map: dict[str, str]
    env: Environment


class ComposeInstanceFiles(NamedTuple):
    env_config_instance: EnvInstanceConfig
    compose_files_source: str
    directory: Path
    compose_files: str
    inline_migrations: dict = None
