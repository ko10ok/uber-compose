from pathlib import Path
from uuid import uuid4

from uber_compose.core.sequence_run_types import DEFAULT_ENV_ID
from uber_compose.core.sequence_run_types import EnvInstanceConfig
from uber_compose.env_description.env_types import Env
from uber_compose.env_description.env_types import Environment
from uber_compose.env_description.env_types import Service
from uber_compose.env_description.env_types import ServiceMode
from uber_compose.helpers.env_id import get_stable_env_id as get_stable_env_id  # noqa: F401
from uber_compose.helpers.env_id import get_template_hash as get_template_hash  # noqa: F401
from uber_compose.helpers.parameterization import build_parameterization_placeholders
from uber_compose.helpers.parameterization import substitute_parameterization_placeholders


def make_env_service_name(service, env_id):
    if env_id == DEFAULT_ENV_ID:
        return service
    return f'{service}-{env_id}'


def sub_env_id(env: Env, placeholders: dict[str, str]) -> Env:
    result_env = Env()
    for key, value in env.items():
        result_env.update({key: substitute_parameterization_placeholders(value, placeholders)})

    return result_env


def prepare_services_env(env: Environment, placeholders: dict[str, str]) -> Environment:
    updated_services = []
    for service_name in env:
        if service_name in env.get_overridden_services_names():
            # skip overridden services
            continue

        updated_services += [
            Service(
                name=env[service_name].name,
                env=sub_env_id(env[service_name].env, placeholders),
                events_handlers=env[service_name].events_handlers,
                mode=env[service_name].mode,
            )
        ]
    new_env = Environment(*updated_services, description=env.description)
    return new_env


def get_new_env_id() -> str:
    env_id = str(uuid4())[:4]
    return env_id


def get_service_map(env: Environment, new_env_id: str):
    return {
        service_name: (
            service_name
            if service.mode in (ServiceMode.OFF, ServiceMode.SINGLETON)
            else make_env_service_name(service_name, new_env_id)
        )
        for service_name, service in env.get_services().items()
        if service.mode != ServiceMode.OFF
    }


def make_env_instance_config(
    env_template: Environment,
    env_id,
    name=None,
    run_id: str | None = None,
    worker_id: int | None = None,
) -> EnvInstanceConfig:
    assert env_template, 'Env template is empty somehow!'
    services_map = get_service_map(env_template, env_id)
    placeholders = build_parameterization_placeholders(
        env_id,
        services_map=services_map,
        run_id=run_id,
        worker_id=worker_id,
    )
    env = prepare_services_env(env_template, placeholders)

    return EnvInstanceConfig(
        env_source=env_template,
        env_name=name,
        env_id=env_id,
        env_services_map=services_map,
        env=env
    )


def get_absolute_compose_files(compose_files: str, env_directory: Path) -> str:
    return ':'.join(
        [
            str(env_directory / compose_file)
            for compose_file in compose_files.split(':')
        ]
    )


def made_up_instance_compose_files(compose_files: str, env_directory: Path) -> str:
    return ':'.join(
        [
            str(env_directory / compose_file.replace('/', '-'))
            for compose_file in compose_files.split(':')
        ]
    )
