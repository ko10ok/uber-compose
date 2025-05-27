from dataclasses import dataclass
from uuid import uuid4

from rich.text import Text

from uber_compose.core.config import Config
from uber_compose.core.docker_compose import ComposeInstance
from uber_compose.core.docker_compose_shell.interface import ComposeShellInterface
from uber_compose.core.sequence_run_types import EMPTY_ID
from uber_compose.core.system_docker_compose import SystemDockerCompose
from uber_compose.core.utils.compose_instance_cfg import get_new_env_id
from uber_compose.env_description.env_types import Environment
from uber_compose.helpers.health_policy import UpHealthPolicy
from uber_compose.output.console import DEFAULT_LOG_POLICY
from uber_compose.output.console import LogPolicy
from uber_compose.output.console import Logger
from uber_compose.output.styles import Style


@dataclass
class ReadyEnv:
    env_id: str
    env: Environment


class UberCompose:
    def __init__(self, log_policy: LogPolicy = DEFAULT_LOG_POLICY, health_policy=UpHealthPolicy()) -> None:
        self.logger = Logger(log_policy)
        self.system_docker_compose = SystemDockerCompose(
            Config().in_docker_project_root_path,
            logger=self.logger
        )
        self.health_policy = health_policy

    async def up(self,
                 config_template: Environment | None = None,
                 compose_files: str | None = None,
                 force_restart: bool = False,
                 release_id: str | None = None,
                 parallelism_limit: int = 1,
                 ) -> ReadyEnv:

        if not compose_files:
            compose_files = self.system_docker_compose.get_default_compose_files()

        if not config_template:
            config_template = self.system_docker_compose.get_default_environment()

        existing_env_id = await self.system_docker_compose.get_env_id_for(config_template, compose_files)
        if existing_env_id and not force_restart:
            self.logger.stage_details(Text(
                'Found suitable ready env: ', style=Style.info
            ).append(Text(existing_env_id, style=Style.mark)))
            env_config = await self.system_docker_compose.get_env_for(config_template, compose_files)
            return ReadyEnv(existing_env_id, env_config)

        if force_restart:
            self.logger.stage_details(Text(
                'Forced restart env', style=Style.info
            ).append(Text(existing_env_id, style=Style.mark)))

        self.logger.stage(Text('Starting new environment', style=Style.info))

        new_env_id = get_new_env_id()
        if release_id is None:
            release_id = str(uuid4())

        if parallelism_limit == 1:
            self.logger.stage_debug(f'Using default service names with {parallelism_limit=}')
            new_env_id = EMPTY_ID

            services = await self.system_docker_compose.get_running_services()
            await self.system_docker_compose.down_services(services)

        compose_instance = ComposeInstance(
            project=Config().project,
            name=str(config_template),
            new_env_id=new_env_id,
            compose_interface=ComposeShellInterface,  # ???
            compose_files=compose_files,
            config_template=config_template,
            in_docker_project_root=Config().in_docker_project_root_path,
            host_project_root_directory=Config().host_project_root_directory,
            except_containers=Config().non_stop_containers,
            tmp_envs_path=Config().tmp_envs_path,
            execution_envs=None,
            release_id=release_id,
            logger=self.logger,
            health_policy=self.health_policy,
        )

        await compose_instance.run()

        # TODO check if ready by state checking

        self.logger.stage_info(Text(f'New environment started'))

        return ReadyEnv(
            new_env_id,
            compose_instance.compose_instance_files.env_config_instance.env,
        )
