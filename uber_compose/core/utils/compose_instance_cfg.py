from pathlib import Path
from uuid import uuid4

from uber_compose.core.sequence_run_types import EMPTY_ID
from uber_compose.core.sequence_run_types import EnvInstanceConfig
from uber_compose.env_description.env_types import Env
from uber_compose.env_description.env_types import Environment
from uber_compose.env_description.env_types import Service
from uber_compose.env_description.env_types import ServiceMode


def make_env_service_name(service, env_id):
    if env_id == EMPTY_ID:
        return service
    return f'{service}-{env_id}'


def sub_env_id(env: Env, services_for_env: dict) -> Env:
    result_env = Env()
    for k, v in env.items():
        for service_replace_from, service_replace_to in services_for_env.items():
            if f'[[{service_replace_from}]]' in v:
                v = v.replace(f'[[{service_replace_from}]]', service_replace_to)
        result_env.update({k: v})

    return result_env


def prepare_services_env(env: Environment, services_map: dict) -> Environment:
    updated_services = []
    for service_name in env:
        if service_name in env.get_overridden_services_names():
            # skip overridden services
            continue

        updated_services += [
            Service(
                name=env[service_name].name,
                env=sub_env_id(env[service_name].env, services_map),
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
        service_name: make_env_service_name(service_name, new_env_id)
        for service_name, service in env.get_services().items() if service.mode != ServiceMode.OFF
    }


def make_env_instance_config(env_template: Environment, env_id, name=None) -> EnvInstanceConfig:
    services_map = get_service_map(env_template, env_id)
    env = prepare_services_env(env_template, services_map)
    assert env_template, 'Env template is empty somehow!'

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
