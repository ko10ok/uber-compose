import shlex
from dataclasses import dataclass
from typing import Callable
from uuid import uuid4

from rich.text import Text

from uber_compose.core.constants import Constants
from uber_compose.core.docker_compose import ComposeInstance
from uber_compose.core.docker_compose_shell.interface import ComposeShellInterface
from uber_compose.core.docker_compose_shell.interface import ProcessExit
from uber_compose.core.sequence_run_types import DEFAULT_ENV_ID
from uber_compose.core.system_docker_compose import SystemDockerCompose
from uber_compose.core.utils.compose_instance_cfg import get_new_env_id
from uber_compose.env_description.env_types import Environment
from uber_compose.env_description.env_types import OverridenService
from uber_compose.helpers.broken_services import calc_broken_services
from uber_compose.helpers.bytes_pickle import base64_pickled
from uber_compose.helpers.bytes_pickle import debase64_pickled
from uber_compose.helpers.exec_result import ExecResult
from uber_compose.helpers.exec_result import ExecTimeout
from uber_compose.helpers.health_policy import UpHealthPolicy
from uber_compose.helpers.jobs_result import JobResult
from uber_compose.helpers.labels import Label
from uber_compose.helpers.singleton import SingletonMeta
from uber_compose.output.console import LogPolicySet
from uber_compose.output.console import Logger
from uber_compose.output.styles import Style
from uber_compose.utils.docker_compose_files_path import get_absolute_compose_files
from uber_compose.utils.services_construction import make_default_environment


@dataclass
class ReadyEnv:
    env_id: str
    env: Environment
    release_id: str


class SystemUberCompose:
    def __init__(self,
                 log_policy: LogPolicySet = None,
                 health_policy=UpHealthPolicy(),
                 cfg_constants: Constants = None,
                 run_id: str = '',
                 ) -> None:
        self.cfg_constants = cfg_constants if cfg_constants else Constants()

        self.logger = Logger(log_policy, self.cfg_constants)

        self.system_docker_compose = SystemDockerCompose(
            self.cfg_constants.in_docker_project_root_path,
            logger=self.logger,
            cfg_constants=self.cfg_constants,
        )
        self.health_policy = health_policy
        self.run_id = run_id
        self.last_release_id = None

    async def up(self,
                 config_template: Environment | None = None,
                 compose_files: str | None = None,
                 force_restart: bool = False,
                 release_id: str | None = None,
                 parallelism_limit: int = 1,
                 services_override: list[OverridenService] | None = None,
                 ) -> ReadyEnv:

        if not compose_files:
            compose_files = self.system_docker_compose.get_default_compose_files()

        if not config_template:
            config_template = make_default_environment(
                compose_files=get_absolute_compose_files(compose_files, self.cfg_constants.in_docker_project_root_path),
            )

        if services_override:
            config_template = config_template.from_environment(config_template, services_override=services_override)

        self.logger.stage_debug(
            f'Searching for environment {config_template} with template: {base64_pickled(config_template)}'
        )
        services_state = await self.system_docker_compose.get_state_for(config_template, compose_files)
        self.logger.stage_details(
            f'Found environments containers: {services_state.as_rich_text()}'
        )
        self.logger.stage_debug(
            f'Found environments containers: {services_state}'
        )
        broken_services = calc_broken_services(services_state, config_template, self.cfg_constants.non_stop_containers)
        if broken_services:
            self.logger.stage(
                Text(
                    f'Not started or broken containers in current environment: ', style=Style.suspicious
                ).append(Text(f'{broken_services}', style=Style.regular))
            )
        if len(services_state) != 0 and len(broken_services) == 0 and not force_restart:
            existing_env_id = services_state.get_any().labels.get(Label.ENV_ID, None)
            env_config = debase64_pickled(services_state.get_any().labels.get(Label.ENV_CONFIG))
            _for = f' for {config_template.description}' if config_template.description else ''
            self.logger.stage_details(Text(
                f'Found suitable{_for} ready env: ', style=Style.info
            ).append(Text(existing_env_id, style=Style.mark)))

            last_release_id = services_state.get_any().labels.get(Label.RELEASE_ID)
            self.last_release_id = last_release_id
            return ReadyEnv(existing_env_id, env_config, last_release_id)

        self.logger.stage_debug(
            f'In-flight containers:\n'
            f'{[(debase64_pickled(service["labels"][Label.ENV_CONFIG_TEMPLATE]), service["labels"][Label.ENV_CONFIG_TEMPLATE]) for service in services_state.as_json()]}'
        )
        if force_restart:
            self.logger.stage_details(Text(
                'Forced restart env', style=Style.info
            ))
            self.logger.stage_debug(Text(
                f'Previous state {services_state.as_json()}', style=Style.info
            ))

        _for = f' {config_template.description}' if config_template.description else ''
        self.logger.stage(Text(f'Starting new{_for} environment', style=Style.info))

        new_env_id = get_new_env_id()
        self.last_release_id = release_id
        if self.last_release_id is None:
            self.last_release_id = str(uuid4())

        if parallelism_limit == 1:
            self.logger.stage_debug(f'Using default service names with {parallelism_limit=}')
            new_env_id = DEFAULT_ENV_ID

            services = await self.system_docker_compose.get_running_services()
            services_to_down = list(set(services) - set(self.cfg_constants.non_stop_containers))
            if services_to_down:
                await self.system_docker_compose.down_services(services_to_down)

        compose_instance = ComposeInstance(
            project=self.cfg_constants.project,
            name=str(config_template),
            new_env_id=new_env_id,
            compose_interface=ComposeShellInterface,  # ???
            compose_files=compose_files,
            config_template=config_template,
            in_docker_project_root=self.cfg_constants.in_docker_project_root_path,
            host_project_root_directory=self.cfg_constants.host_project_root_directory,
            except_containers=self.cfg_constants.non_stop_containers,
            tmp_envs_path=self.cfg_constants.tmp_envs_path,
            execution_envs=None,
            release_id=self.last_release_id,
            logger=self.logger,
            health_policy=self.health_policy,
            run_id=self.run_id,
        )

        await compose_instance.run()

        # TODO check if ready by state checking

        self.logger.stage_info(Text(f'New environment started'))

        return ReadyEnv(
            new_env_id,
            compose_instance.compose_instance_files.env_config_instance.env,
            self.last_release_id,
        )

    async def exec(self,
                   container: str,
                   command: str,
                   extra_env: dict[str, str] = None,
                   wait: Callable | ProcessExit | None = ProcessExit(),
                   env_id: str = DEFAULT_ENV_ID,
                   ) -> ExecResult | ExecTimeout:
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
        res = await dc_shell.dc_exec_until_state(container, cmd, extra_env=extra_env, wait=wait)

        job_result, stdout, stderr = await dc_shell.dc_exec(container, f'cat /tmp/{log_file}')
        if job_result != JobResult.GOOD:
            self.logger.error(Text(f'Error executing command in container {container}: {stderr}'))

        if not res.check_result:
            return ExecTimeout(stdout=stdout, cmd=command)

        return ExecResult(stdout=stdout, cmd=command)


class UberCompose(SystemUberCompose):
    """
    UberCompose is client class for managing Docker Compose environments.
    """
    ...


class TheUberCompose(SystemUberCompose, metaclass=SingletonMeta):
    """
    TheUberCompose is unified instance of env manager for all scenarios.
    """
    ...
