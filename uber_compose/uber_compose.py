from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import shlex
from typing import Any
from typing import Callable
from uuid import uuid4

from rich.text import Text

from uber_compose.core.constants import Constants
from uber_compose.core.docker_compose import ComposeInstance
from uber_compose.core.docker_compose_shell.interface import ComposeShellInterface
from uber_compose.core.docker_compose_shell.interface import ProcessExit
from uber_compose.core.docker_compose_shell.interface import TimeOutCheck
from uber_compose.core.docker_compose_shell.types import ExecLifeCyclePolicy
from uber_compose.core.docker_compose_shell.types import ServicesComposeState
from uber_compose.core.sequence_run_types import DEFAULT_ENV_ID
from uber_compose.core.system_docker_compose import SystemDockerCompose
from uber_compose.core.utils.compose_instance_cfg import get_new_env_id
from uber_compose.core.utils.compose_instance_cfg import get_stable_env_id
from uber_compose.core.utils.state_waiting import is_service_not_running_or_not_healthy
from uber_compose.env_description.env_types import DEFAULT_ENV_DESCRIPTION
from uber_compose.env_description.env_types import Environment
from uber_compose.env_description.env_types import OverridenService
from uber_compose.env_description.env_types import ServiceMode
from uber_compose.errors.mounted_files import MountedFileNotFoundError
from uber_compose.errors.up import SingletonConfigChangedError
from uber_compose.helpers.broken_services import calc_broken_services
from uber_compose.helpers.bytes_pickle import base64_pickled
from uber_compose.helpers.bytes_pickle import debase64_pickled
from uber_compose.helpers.current_env import get_current_env_context
from uber_compose.helpers.current_env import get_current_env_id
from uber_compose.helpers.current_env import get_run_depth
from uber_compose.helpers.current_env import is_child_project as _is_child_project
from uber_compose.helpers.exec_result import ExecResult
from uber_compose.helpers.exec_result import ExecTimeout
from uber_compose.helpers.health_policy import UpHealthPolicy
from uber_compose.helpers.hooks import HooksRegistry
from uber_compose.helpers.hooks import UberComposeEvent
from uber_compose.helpers.jobs_result import JobResult
from uber_compose.helpers.labels import Label
from uber_compose.helpers.singleton import SingletonMeta
from uber_compose.helpers.workers_per_env import normalize_workers_per_env
from uber_compose.output.console import LogPolicySet
from uber_compose.output.console import Logger
from uber_compose.output.styles import Style
from uber_compose.parallel_plugin.worker_api import get_worker_id
from uber_compose.utils.docker_compose_files_path import get_absolute_compose_files
from uber_compose.utils.services_construction import make_default_environment


@dataclass
class ReadyEnv:
    env_id: str
    env: Environment
    release_id: str


def _env_identity(config_template: Environment) -> tuple:
    return tuple(sorted(
        (service.name, service.mode.value)
        for service in config_template.get_services().values()
    ))


def _service_config(service) -> tuple:
    return (
        service.name,
        tuple(sorted(service.env.items())),
        tuple(service.events_handlers),
        service.mode,
        tuple(service.mounted_files),
    )


@lru_cache(maxsize=512)
def _service_mode_from_recorded_template(recorded_template: str, container: str) -> ServiceMode | None:
    try:
        recorded_env = debase64_pickled(recorded_template)
    except Exception:
        return None

    recorded_service = recorded_env.get_services().get(container)
    return recorded_service.mode if recorded_service is not None else None


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
        self._previous_release_id: str | None = None
        self._previous_env_identity: tuple | None = None
        self._hooks = HooksRegistry()

    def on(self, event: UberComposeEvent, func: Callable, *args: Any, **kwargs: Any) -> None:
        self._hooks.on(event, func, *args, **kwargs)

    @staticmethod
    def current_env_id() -> str:
        return get_current_env_id()

    def mounted_files_dir(self) -> Path:
        return self.cfg_constants.mounted_files_path

    def mounted_file_path(self, relative_path: str | Path) -> Path:
        relative_path = Path(relative_path)
        if relative_path.is_absolute():
            raise ValueError(
                f'mounted_file_path expects a relative path, got absolute path: {relative_path}'
            )

        env_id = get_current_env_id()
        mounted_files_dir = self.mounted_files_dir()
        searched_path = mounted_files_dir / env_id / relative_path
        if not searched_path.is_file():
            raise MountedFileNotFoundError(
                relative_path,
                env_id,
                searched_path,
                mounted_files_dir,
                self.cfg_constants.in_docker_project_root_path,
            )

        return searched_path

    @staticmethod
    def current_env_context():
        return get_current_env_context()

    @staticmethod
    def current_env():
        return get_current_env_context().env

    @staticmethod
    def current_service_env(service_name: str) -> dict[str, Any] | None:
        env = get_current_env_context().env
        if env is None or service_name not in env:
            return None
        return dict(env[service_name].env)

    @staticmethod
    def current_service_env_param(service_name: str, param: str, default=None):
        service_env = SystemUberCompose.current_service_env(service_name)
        if service_env is None:
            return default
        return service_env.get(param, default)

    @staticmethod
    def current_worker_id() -> int:
        return get_current_env_context().worker_id

    @staticmethod
    def current_workers_total() -> int:
        return get_current_env_context().workers_total

    @staticmethod
    def is_current_worker_parallel() -> bool:
        return get_current_env_context().workers_total > 1

    @staticmethod
    def current_replica_index() -> int | None:
        return get_current_env_context().replica_index

    @staticmethod
    def current_replicas_total() -> int | None:
        return get_current_env_context().replicas_total

    @staticmethod
    def current_namespace() -> str:
        context = get_current_env_context()
        return context.namespace or context.env_id

    @staticmethod
    def current_worker_groups() -> list[str]:
        return list(get_current_env_context().groups)

    @staticmethod
    def current_run_id() -> str | None:
        return get_current_env_context().run_id

    @staticmethod
    def current_run_depth() -> int:
        return get_run_depth()

    @staticmethod
    def is_child_project() -> bool:
        return _is_child_project()

    async def up(self,
                 config_template: Environment | None = None,
                 compose_files: str | None = None,
                 force_restart: bool = False,
                 release_id: str | None = None,
                 parallelism_limit: int = 1,
                 services_override: list[OverridenService] | None = None,
                 env_id: str | None = None,
                 ) -> ReadyEnv:

        compose_files = self._resolve_compose_files(compose_files)
        config_template = self._resolve_config_template(config_template, compose_files, services_override)

        requested_env_id = env_id if parallelism_limit > 1 else None
        services_state = await self._get_current_state(config_template, compose_files)
        if requested_env_id is not None:
            services_state = services_state.get_all_for(
                lambda service_state: service_state.check(Label.ENV_ID, requested_env_id)
            )

        protected_singleton_services = await self._compute_singleton_protected_services(
            config_template, force_restart
        )
        reusable_env = self._find_reusable_env(
            services_state,
            config_template,
            force_restart,
            protected_singleton_services,
        )
        if reusable_env is not None:
            await self._hooks.run(UberComposeEvent.AFTER_UP)
            return reusable_env

        self._log_inflight_and_restart_info(services_state, force_restart)

        return await self._start_new_environment(
            config_template, compose_files, release_id, parallelism_limit, force_restart,
            requested_env_id=requested_env_id,
            protected_singleton_services=protected_singleton_services,
        )

    async def prepare_parallel_environments(
        self,
        config_templates: list[Environment | None],
        compose_files: str | None = None,
        workers_per_env: dict[str, int] | None = None,
        default_workers_per_env: int = 1,
        force_restart: bool = False,
        services_override: list[OverridenService] | None = None,
    ) -> list[ReadyEnv]:
        compose_files = self._resolve_compose_files(compose_files)
        workers_per_env = normalize_workers_per_env(workers_per_env)

        resolved = []
        for config_template in config_templates:
            resolved_template = self._resolve_config_template(
                config_template, compose_files, services_override
            )
            replicas = self._env_replicas(config_template, workers_per_env, default_workers_per_env)
            resolved.append((resolved_template, replicas))

        total_replicas = sum(replicas for _, replicas in resolved)
        if workers_per_env is None:
            ready_envs = []
            for resolved_template, _ in resolved:
                ready_envs.append(await self.up(
                    config_template=resolved_template,
                    compose_files=compose_files,
                    force_restart=force_restart,
                    parallelism_limit=1,
                ))
            return ready_envs

        parallelism_limit = max(total_replicas, 2)
        ready_envs = []
        for resolved_template, replicas in resolved:
            desired_env_ids = [
                get_stable_env_id(resolved_template, index)
                for index in range(replicas)
            ]
            for env_id in desired_env_ids:
                ready_envs.append(await self.up(
                    config_template=resolved_template,
                    compose_files=compose_files,
                    force_restart=force_restart,
                    parallelism_limit=parallelism_limit,
                    env_id=env_id,
                ))
            await self._down_extra_replicas(resolved_template, compose_files, desired_env_ids)
        return ready_envs

    async def melt_down_extra_replicas(
        self,
        config_template: Environment | None,
        compose_files: str | None = None,
        desired_env_ids: list[str] | None = None,
        services_override: list[OverridenService] | None = None,
    ) -> None:
        compose_files = self._resolve_compose_files(compose_files)
        resolved_template = self._resolve_config_template(
            config_template, compose_files, services_override
        )
        await self._down_extra_replicas(
            resolved_template,
            compose_files,
            list(desired_env_ids or []),
        )

    def _env_replicas(
        self,
        config_template: Environment | None,
        workers_per_env: dict[str, int] | None,
        default_workers_per_env: int,
    ) -> int:
        replicas = default_workers_per_env
        if workers_per_env:
            env_key = (
                config_template.description
                if config_template is not None
                else DEFAULT_ENV_DESCRIPTION
            )
            replicas = workers_per_env.get(env_key, default_workers_per_env)
        return max(int(replicas), 1)

    async def _down_extra_replicas(
        self,
        config_template: Environment,
        compose_files: str,
        desired_env_ids: list[str],
    ) -> None:
        desired = set(desired_env_ids)
        services_state = await self.system_docker_compose.get_state_for(config_template, compose_files)

        extra_services = []
        for service_state in services_state:
            env_id = service_state.labels.get(Label.ENV_ID)
            if env_id in desired:
                continue
            if service_state.name in self.cfg_constants.non_stop_containers:
                continue
            extra_services.append(service_state.name)

        if extra_services:
            self.logger.stage(Text(
                'Downing extra env replicas: ', style=Style.info
            ).append(Text(f'{extra_services}', style=Style.regular)))
            await self.system_docker_compose.down_services(extra_services)

    def _resolve_compose_files(self, compose_files: str | None) -> str:
        if not compose_files:
            compose_files = self.system_docker_compose.get_default_compose_files()
        return compose_files

    def _resolve_config_template(
        self,
        config_template: Environment | None,
        compose_files: str,
        services_override: list[OverridenService] | None,
    ) -> Environment:
        if not config_template:
            config_template = make_default_environment(
                compose_files=get_absolute_compose_files(compose_files, self.cfg_constants.in_docker_project_root_path),
            )

        if services_override:
            config_template = config_template.from_environment(config_template, services_override=services_override)

        return config_template

    async def _get_current_state(self, config_template: Environment, compose_files: str) -> ServicesComposeState:
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
        return services_state

    def _should_restart(self, services_state: ServicesComposeState, broken_services: list, force_restart: bool) -> bool:
        return len(services_state) == 0 or len(broken_services) != 0 or force_restart

    def _find_reusable_env(
        self,
        services_state: ServicesComposeState,
        config_template: Environment,
        force_restart: bool,
        protected_singleton_services: list[str] | None = None,
    ) -> ReadyEnv | None:
        excluded_from_check = self.cfg_constants.non_stop_containers + list(protected_singleton_services or [])
        broken_services = calc_broken_services(services_state, config_template, excluded_from_check)
        if broken_services:
            self.logger.stage(
                Text(
                    'Not started or not ready containers in current environment: ', style=Style.suspicious
                ).append(Text(f'{broken_services}', style=Style.regular))
            )

        if self._should_restart(services_state, broken_services, force_restart):
            return None

        existing_env_id = services_state.get_any().labels.get(Label.ENV_ID, None)
        env_config = debase64_pickled(services_state.get_any().labels.get(Label.ENV_CONFIG))
        _for = f' for {config_template.description}' if config_template.description else ''
        self.logger.stage_details(Text(
            f'Found suitable{_for} ready env: ', style=Style.info
        ).append(Text(existing_env_id, style=Style.mark)))

        last_release_id = services_state.get_any().labels.get(Label.RELEASE_ID)
        self.last_release_id = last_release_id
        self._previous_release_id = last_release_id
        self._previous_env_identity = _env_identity(config_template)
        return ReadyEnv(existing_env_id, env_config, last_release_id)

    def _log_inflight_and_restart_info(self, services_state: ServicesComposeState, force_restart: bool) -> None:
        in_flight_templates = [
            (
                debase64_pickled(service["labels"][Label.ENV_CONFIG_TEMPLATE]),
                service["labels"][Label.ENV_CONFIG_TEMPLATE],
            )
            for service in services_state.as_json()
        ]
        self.logger.stage_debug(
            f'In-flight containers:\n'
            f'{in_flight_templates}'
        )
        if force_restart:
            self.logger.stage_details(Text(
                'Forced restart env', style=Style.info
            ))
            self.logger.stage_debug(Text(
                f'Previous state {services_state.as_json()}', style=Style.info
            ))

    async def _compute_singleton_protected_services(
        self,
        config_template: Environment,
        force_restart: bool,
    ) -> list[str]:
        """
        Services that must survive this (re)start untouched: currently running, healthy,
        and marked ServiceMode.SINGLETON — either in the new config_template (if declared
        there) or, when absent from it, in the config_template that created the running
        container (read back from its own ENV_CONFIG_TEMPLATE label).

        An explicit force_restart bypasses this protection entirely.
        """
        # TODO: force_restart of a shared singleton should eventually cascade to all
        # dependent services/environments instead of silently restarting a singleton that
        # another parallel environment may still rely on.
        if force_restart:
            return []

        declared_services = config_template.get_services()
        all_services_state = await self.system_docker_compose.get_all_services_state()

        protected_services = []
        for service_state in all_services_state:
            if is_service_not_running_or_not_healthy(service_state):
                continue

            declared_service = declared_services.get(service_state.name)
            recorded_template = service_state.labels.get(Label.ENV_CONFIG_TEMPLATE)
            recorded_service = (
                debase64_pickled(recorded_template).get_services().get(service_state.name)
                if recorded_template else None
            )
            declared_mode = declared_service.mode if declared_service is not None else None
            recorded_mode = recorded_service.mode if recorded_service is not None else None

            if declared_service is not None and recorded_service is not None:
                singleton_is_involved = (
                    declared_mode == ServiceMode.SINGLETON
                    or recorded_mode == ServiceMode.SINGLETON
                )
                if (
                    singleton_is_involved
                    and declared_mode == ServiceMode.SINGLETON
                    and _service_config(declared_service) != _service_config(recorded_service)
                ):
                    raise SingletonConfigChangedError(
                        f'Singleton service "{service_state.name}" configuration must not change while it is running. '
                        f'Running config: {_service_config(recorded_service)!r}. '
                        f'Requested config: {_service_config(declared_service)!r}. '
                        f'Use force_restart if this change is intentional.'
                    )

            service_mode = declared_mode if declared_service is not None else recorded_mode

            if service_mode == ServiceMode.SINGLETON or recorded_mode == ServiceMode.SINGLETON:
                protected_services.append(service_state.name)

        return protected_services

    async def _down_existing_env_containers(self, env_id: str, except_containers: list[str]) -> None:
        services_state = await self.system_docker_compose.get_all_services_state()
        services_to_down = [
            service_state.name
            for service_state in services_state
            if service_state.labels.get(Label.ENV_ID) == env_id
            and service_state.name not in except_containers
        ]
        if not services_to_down:
            return

        self.logger.stage(
            Text('Downing existing env containers: ', style=Style.info)
            .append(Text(f'{services_to_down}', style=Style.regular))
        )
        await self.system_docker_compose.down_services(services_to_down)

    async def _start_new_environment(
        self,
        config_template: Environment,
        compose_files: str,
        release_id: str | None,
        parallelism_limit: int,
        force_restart: bool = False,
        requested_env_id: str | None = None,
        protected_singleton_services: list[str] | None = None,
    ) -> ReadyEnv:
        _for = f' {config_template.description}' if config_template.description else ''
        self.logger.stage(Text(f'Starting new{_for} environment', style=Style.info))
        self.logger.stage_details(f'Use compose files: {compose_files}')

        new_env_id = requested_env_id or get_new_env_id()
        self.last_release_id = release_id
        if self.last_release_id is None:
            self.last_release_id = str(uuid4())

        current_env_identity = _env_identity(config_template)
        is_env_update = (
            self._previous_release_id is not None
            and self._previous_env_identity == current_env_identity
        )

        if protected_singleton_services is None:
            protected_singleton_services = await self._compute_singleton_protected_services(
                config_template, force_restart
            )
        if protected_singleton_services:
            self.logger.stage_debug(
                f'Protecting singleton services from restart: {protected_singleton_services}'
            )

        if parallelism_limit == 1:
            self.logger.stage_debug(f'Using default service names with {parallelism_limit=}')
            new_env_id = DEFAULT_ENV_ID

            services = await self.system_docker_compose.get_running_services()
            services_to_down = list(
                set(services)
                - set(self.cfg_constants.non_stop_containers)
                - set(protected_singleton_services)
            )
            if services_to_down:
                await self.system_docker_compose.down_services(services_to_down)
        else:
            await self._down_existing_env_containers(
                new_env_id,
                self.cfg_constants.non_stop_containers + protected_singleton_services,
            )

        compose_instance = ComposeInstance(
            project=self.cfg_constants.project,
            name=str(config_template),
            new_env_id=new_env_id,
            compose_interface=ComposeShellInterface,  # ???
            compose_files=compose_files,
            config_template=config_template,
            in_docker_project_root=self.cfg_constants.in_docker_project_root_path,
            host_project_root_directory=self.cfg_constants.host_project_root_directory,
            except_containers=self.cfg_constants.non_stop_containers + protected_singleton_services,
            tmp_envs_path=self.cfg_constants.tmp_envs_path,
            execution_envs=None,
            release_id=self.last_release_id,
            logger=self.logger,
            health_policy=self.health_policy,
            run_id=self.run_id,
            worker_id=get_worker_id(),
            mounted_files_path=self.cfg_constants.mounted_files_path,
            mounted_files_host_path=self.cfg_constants.mounted_files_host_path,
        )

        await compose_instance.run()

        # TODO check if ready by state checking

        self.logger.stage_info(Text('New environment started'))

        await self._hooks.run(UberComposeEvent.AFTER_UP)
        if is_env_update:
            await self._hooks.run(UberComposeEvent.AFTER_UPDATED_ENV_UP)
        self._previous_release_id = self.last_release_id
        self._previous_env_identity = current_env_identity

        return ReadyEnv(
            new_env_id,
            compose_instance.compose_instance_files.env_config_instance.env,
            self.last_release_id,
        )

    def _service_mode_for_state(self, service_state, container: str) -> ServiceMode | None:
        recorded_template = service_state.labels.get(Label.ENV_CONFIG_TEMPLATE)
        if not recorded_template:
            recorded_template = service_state.labels.get(Label.ENV_CONFIG)
        if not recorded_template:
            return None

        return _service_mode_from_recorded_template(recorded_template, container)

    def _resolve_exec_service_state(
        self,
        dc_state: ServicesComposeState,
        container: str,
        env_id: str,
    ):
        service_states = dc_state.get_all_for(
            lambda service_state: service_state.check(Label.TEMPLATE_SERVICE_NAME, container)
        )

        exact_service_states = service_states.get_all_for(
            lambda service_state: service_state.check(Label.ENV_ID, env_id)
        )
        if len(exact_service_states.as_json()) == 1:
            return exact_service_states.get_any()

        singleton_service_states = service_states.get_all_for(
            lambda service_state: self._service_mode_for_state(service_state, container)
            == ServiceMode.SINGLETON
        )
        if len(singleton_service_states.as_json()) == 1:
            return singleton_service_states.get_any()

        available_env_ids = sorted({
            service.labels.get(Label.ENV_ID)
            for service in service_states
        })
        singleton_details = ''
        if len(singleton_service_states.as_json()) > 1:
            singleton_env_ids = sorted({
                service.labels.get(Label.ENV_ID)
                for service in singleton_service_states
            })
            singleton_details = f' Multiple singleton environments: {singleton_env_ids}.'

        raise ValueError(
            f'Container {container} not found in environment {env_id}. '
            f'Available environments for this container: {available_env_ids}.'
            f'{singleton_details} '
            f'Pass env_id explicitly when multiple namespaces are running.'
        )

    async def exec(self,
                   container: str,
                   command: str,
                   extra_env: dict[str, str] = None,
                   wait: Callable[..., bool] | ProcessExit | None = ProcessExit(),
                   env_id: str | None = None,
                   timeout: TimeOutCheck = None,
                   life_cycle_policy: ExecLifeCyclePolicy = ExecLifeCyclePolicy()
                   ) -> ExecResult | ExecTimeout:
        if env_id is None:
            env_id = get_current_env_id()

        uid = str(uuid4())
        log_file = f'{uid}.log'

        dc_shell = self.system_docker_compose.get_dc_shell()

        dc_state = await dc_shell.dc_state()
        assert isinstance(dc_state, ServicesComposeState), f'Got error: {dc_state}'

        service_state = self._resolve_exec_service_state(dc_state, container, env_id)
        container = service_state.labels[Label.SERVICE_NAME]

        cmd = f'sh -c \'{shlex.quote(command)[1:-1]} > /tmp/{log_file} 2>&1\''
        res = await dc_shell.dc_exec_until_state(
            container=container,
            cmd=cmd,
            extra_env=extra_env,
            wait=wait,
            timeout=timeout,
            kill_before=life_cycle_policy.kill_before_same_old_command_running,
            kill_after=life_cycle_policy.kill_after_command_still_running,
            break_on_timeout=life_cycle_policy.break_on_timeout,
        )

        job_result, stdout, stderr = await dc_shell.dc_exec(container, f'cat /tmp/{log_file}')
        if job_result != JobResult.GOOD:
            self.logger.error(Text(f'Error executing command in container {container}: {stderr}'))

        if not res.finished:
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
