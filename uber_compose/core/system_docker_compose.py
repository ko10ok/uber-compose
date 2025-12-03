import pprint
from itertools import groupby
from pathlib import Path

from rich.text import Text
from uber_compose.core.constants import Constants
from uber_compose.core.docker_compose_shell.interface import ComposeShellInterface
from uber_compose.core.docker_compose_shell.types import ServicesComposeState
from uber_compose.core.utils.compose_instance_cfg import get_service_map
from uber_compose.env_description.env_types import Environment
from uber_compose.helpers.bytes_pickle import base64_pickled
from uber_compose.helpers.bytes_pickle import debase64_pickled
from uber_compose.helpers.labels import Label
from uber_compose.output.console import CONSOLE
from uber_compose.output.console import Logger
from uber_compose.output.styles import Style
from uber_compose.utils.docker_compose_files_path import get_absolute_compose_files
from uber_compose.utils.search_docker_compose_files import scan_for_compose_files
from uber_compose.utils.services_construction import make_default_environment


class SystemDockerCompose:
    def __init__(self, inner_project_root: Path, logger: Logger, cfg_constants: Constants = None) -> None:
        self.cfg_constants = cfg_constants if cfg_constants else Constants()
        self.logger = logger

        # TODO get path from Constants. Could be used in cases dc yaml not in root directory
        self.default_compose_files = ':'.join(
            scan_for_compose_files(inner_project_root, self.cfg_constants.docker_compose_files_scan_depth)
        )
        self.logger.commands(f'Found default compose files: {self.default_compose_files}')
        assert self.default_compose_files, f'No docker-compose files found in the project root {inner_project_root} directory.'

        self.default_environment = make_default_environment(
            compose_files=get_absolute_compose_files(self.default_compose_files, inner_project_root),
        )
        self.dc_shell = ComposeShellInterface(
            self.default_compose_files,
            inner_project_root,
            logger=logger,
            cfg_constants=self.cfg_constants,
        )

    def get_default_compose_files(self) -> str:
        return self.default_compose_files

    def get_default_environment(self) -> Environment:
        return self.default_environment

    def get_dc_shell(self) -> ComposeShellInterface:
        return self.dc_shell

    async def get_state_for(self, config_template: Environment, compose_files: str) -> ServicesComposeState:
        services_state = await self.dc_shell.dc_state()
        services_states = services_state.get_all_for(
            lambda service_state: (
                service_state.check(Label.ENV_CONFIG_TEMPLATE, base64_pickled(Environment.from_environment(config_template)))
                and service_state.check(Label.COMPOSE_FILES, compose_files)
            )
        )
        return services_states

    async def get_env_for(self, config_template: Environment, compose_files: str) -> Environment:
        services_states = await self.get_state_for(config_template, compose_files)

        if not services_states.as_json():
            return None

        service_state = services_states.get_any()

        env_hash = service_state.labels.get(Label.ENV_CONFIG, None)
        assert env_hash, f'Env config hash not found for {service_state.as_json()}'

        return debase64_pickled(env_hash)

    async def get_env_id_for(self, config_template: Environment, compose_files: str) -> str | None:
        services_states = await self.get_state_for(config_template, compose_files)

        self.logger.stage_details(
            Text(f'Found {len(services_states.as_json())} services for env template: ', style=Style.info).append(
                Text(
                    f'\n{pprint.pformat(config_template.as_json())} '
                    f'\nHash: {base64_pickled(config_template)}', style=Style.regular
                )
            )
        )
        if not services_states.as_json():
            return None

        env_id = services_states.get_any().labels.get(Label.ENV_ID, None)

        # # check all up or ok-exited
        # map_service = get_service_map(config_template, env_id)
        # services_names = dict(groupby(services_states.as_json(), lambda x: x['name']))
        # for service_name in set(config_template.get_services()) - set(Constants().non_stop_containers):
        #     mapped_name = map_service.get(service_name, None)
        #     # TODO check services is ok or ok-exited
        #     if mapped_name not in services_names:
        #         self.logger.stage_details(Text(f"Service {service_name} isn't ready",style=Style.suspicious))
        #         return None

        return env_id

    async def get_running_services(self) -> list[str]:
        services_state = await self.dc_shell.dc_state()
        return [service.name for service in services_state.get_all_for()]

    async def down_services(self, services: list[str] | None = None) -> None:
        await self.dc_shell.dc_down(services=services)
