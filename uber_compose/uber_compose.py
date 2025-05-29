import shlex
from dataclasses import dataclass
from typing import Callable
from uuid import uuid4

from rich.text import Text

from uber_compose.core.constants import Constants
from uber_compose.core.docker_compose import ComposeInstance
from uber_compose.core.docker_compose_shell.interface import ComposeShellInterface
from uber_compose.core.docker_compose_shell.interface import ProcessExit
from uber_compose.core.sequence_run_types import EMPTY_ID
from uber_compose.core.system_docker_compose import SystemDockerCompose
from uber_compose.core.utils.compose_instance_cfg import get_new_env_id
from uber_compose.env_description.env_types import Environment
from uber_compose.helpers.health_policy import UpHealthPolicy
from uber_compose.helpers.jobs_result import JobResult
from uber_compose.helpers.labels import Label
from uber_compose.output.console import LogPolicySet
from uber_compose.output.console import LogPolicy
from uber_compose.output.console import Logger
from uber_compose.output.styles import Style


@dataclass
class ReadyEnv:
    env_id: str
    env: Environment


class UberCompose:
    def __init__(self, log_policy: LogPolicySet = None, health_policy=UpHealthPolicy()) -> None:
        self.logger = Logger(log_policy)
        self.system_docker_compose = SystemDockerCompose(
            Constants().in_docker_project_root_path,
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
            project=Constants().project,
            name=str(config_template),
            new_env_id=new_env_id,
            compose_interface=ComposeShellInterface,  # ???
            compose_files=compose_files,
            config_template=config_template,
            in_docker_project_root=Constants().in_docker_project_root_path,
            host_project_root_directory=Constants().host_project_root_directory,
            except_containers=Constants().non_stop_containers,
            tmp_envs_path=Constants().tmp_envs_path,
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

    async def exec(self, env_id: str, container: str, command, extra_env: dict[str, str] = None,
                   until: Callable | ProcessExit | None = ProcessExit(),
                   ):
        uid = str(uuid4())
        log_file = f'{uid}.log'

        dc_shell = self.system_docker_compose.get_dc_shell()

        dc_state = await dc_shell.dc_state()
        service_state = dc_state.get_all_for(
            lambda service_state: service_state.check(Label.ENV_ID, env_id)
                                  and service_state.check(Label.TEMPLATE_SERVICE_NAME, container)
        )
        if len(service_state.as_json()) != 1:
            raise ValueError(f'Container {container} not found in environment {env_id}')

        container = service_state.get_any().labels[Label.SERVICE_NAME]

        cmd = f'sh -c \'{shlex.quote(command)[1:-1]} > /tmp/{log_file} 2>&1\''
        await dc_shell.dc_exec_until_state(container, cmd, extra_env=extra_env, until=until)

        job_result, stdout, stderr = await dc_shell.dc_exec(container, f'cat /tmp/{log_file}')
        if job_result != JobResult.GOOD:
            self.logger.error(Text(f'Error executing command in container {container}: {stderr}'))

        return stdout
