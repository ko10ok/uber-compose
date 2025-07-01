import os
import sys
from asyncio import sleep
from pathlib import Path

from rich.text import Text

from uber_compose.core.constants import Constants
from uber_compose.core.docker_compose_shell.interface import ComposeShellInterface
from uber_compose.core.sequence_run_types import ComposeInstanceFiles
from uber_compose.core.sequence_run_types import EnvInstanceConfig
from uber_compose.core.utils.compose_files import get_compose_services_dependency_tree
from uber_compose.core.utils.compose_files import make_env_compose_instance_files
from uber_compose.core.utils.compose_instance_cfg import make_env_instance_config
from uber_compose.core.utils.state_waiting import wait_all_services_up
from uber_compose.env_description.env_types import Environment
from uber_compose.env_description.env_types import EventStage
from uber_compose.errors.up import ServicesUpError
from uber_compose.helpers.health_policy import UpHealthPolicy
from uber_compose.helpers.jobs_result import JobResult
from uber_compose.output.console import Logger
from uber_compose.output.styles import Style

INFLIGHT = 'inflight'


class ComposeInstance:
    def __init__(self,
                 project: str,
                 name: str,  # sometimes differs from Env.name in example DEFAULT_dev for different dc set
                 new_env_id: str,
                 compose_interface: type[ComposeShellInterface],  # = ComposeShellInterface
                 compose_files: str,
                 config_template: Environment | None,
                 in_docker_project_root: Path,
                 host_project_root_directory: Path,
                 except_containers: list[str],
                 tmp_envs_path: Path,
                 run_id: str,
                 execution_envs: dict = None,
                 release_id: str = None,
                 logger: Logger = None,
                 health_policy: UpHealthPolicy = UpHealthPolicy(),
                 ):
        self.run_id = run_id
        self.logger = logger
        self.health_policy = health_policy
        self.compose_files = compose_files
        self.in_docker_project_root = in_docker_project_root
        self.host_project_root_directory = host_project_root_directory
        self.except_containers = except_containers
        self.tmp_envs_path = tmp_envs_path

        self.project = project
        if execution_envs is None:
            self.execution_envs = dict(os.environ)

        self.new_env_id = new_env_id
        self.name = name
        self.config_template = config_template
        self._env_instance_config = None
        self.compose_interface = compose_interface

        self.release_id: str = release_id

        self.compose_instance_files: ComposeInstanceFiles = None
        for file in self.compose_files.split(':'):
            assert (file := Path(self.in_docker_project_root / file)).exists(), f'File {file} doesnt exist'

    async def config(self) -> EnvInstanceConfig:
        if self._env_instance_config is None:
            self._env_instance_config = make_env_instance_config(
                env_template=self.config_template,
                env_id=self.new_env_id,
                name=self.name,
            )
        return self._env_instance_config

    async def generate_config_files(self) -> ComposeInstanceFiles:
        assert self.new_env_id != INFLIGHT, 'somehow regenerated files for inflight env'
        compose_instance_files = make_env_compose_instance_files(
            await self.config(),
            self.compose_files,
            project_network_name=self.project,
            host_project_root_directory=self.host_project_root_directory,
            compose_files_path=self.in_docker_project_root,
            tmp_env_path=self.tmp_envs_path,
            release_id=self.release_id,
            run_id=self.run_id,
        )
        # TODO uneven compose_executor initialization!! but compose_interface compose_files-dependent
        self.compose_executor = self.compose_interface(
            compose_files=compose_instance_files.compose_files,
            in_docker_project_root=self.in_docker_project_root,
            logger=self.logger,
        )
        return compose_instance_files

    async def run_migration(self, stages, services, env_config_instance, migrations):
        for service in env_config_instance.env:
            sys.stdout.flush()
            if service not in services:
                continue

            for handler in migrations[service]:
                if handler.stage not in stages:
                    continue

                # TODO fix service map if default env
                target_service = env_config_instance.env_services_map[handler.executor or service]

                # TODO check if need to template migrations
                #   substituted_cmd = handler.cmd.format(**env_config_instance.env_services_map)
                substituted_cmd = handler.cmd
                migrate_result = await self.compose_executor.dc_exec_until_state(
                    target_service, substituted_cmd,
                    kill_before=False,
                    kill_after=False,
                )
                if not migrate_result.check_result:
                    services_status = await self.compose_executor.dc_state()
                    error = Text(f"Can't migrate service {target_service}, with {substituted_cmd}", style=Style.bad).append(
                        Text(f"\n{migrate_result.stdout=}\n",style=Style.regular)
                    ).append(
                        Text(f"{migrate_result.stderr=}", style=Style.bad)
                    ).append(
                        services_status.as_rich_text()
                    )
                    self.logger.error(error)
                    self.logger.error_details(f"\nServices logs:\n {await self.logs(services)}")
                    raise ServicesUpError(f"Can't migrate service {target_service}, with {substituted_cmd}"
                                          f"\n{migrate_result.stdout=}\n{migrate_result.stderr=}"
                                          f"\nServices status:\n {services_status.as_rich_text()}") from None

    async def run_services_pack(self, services: list[str], migrations):

        for container in self.except_containers:
            if container in services:
                services.remove(container)
        self.logger.stage_details(f'Starting services pack: {services}; except: {self.except_containers}')

        status_result = await self.compose_executor.dc_state()
        assert status_result != JobResult.BAD, f"Can't get first status for services {services}"

        await self.run_migration(
            [EventStage.BEFORE_SERVICE_START],
            services,
            self.compose_instance_files.env_config_instance,
            migrations
        )

        up_result = await self.compose_executor.dc_up(services)
        if up_result != JobResult.GOOD:
            services_status = await self.compose_executor.dc_state()
            raise ServicesUpError(
                f"Can't up services {services} for "
                f"{self.health_policy.service_up_check_attempts * self.health_policy.service_up_check_delay_s}s"
                f"\nWith error: {up_result}"
                f"\nServices status:\n {services_status.as_rich_text()}"
            ) from None


        await self.run_migration(
            [EventStage.AFTER_SERVICE_START],
            services,
            self.compose_instance_files.env_config_instance,
            migrations
        )

        # up process asynchronous
        # check services started before migrations if health policy told to do that:

        await sleep(self.health_policy.pre_check_delay_s)
        if self.health_policy.wait_for_healthy_in_between:
            check_up_result = await wait_all_services_up(
                attempts=self.health_policy.service_up_check_attempts,
                delay_s=self.health_policy.service_up_check_delay_s,
                logger_func=self.logger.stage_details,
                get_compose_state=self.compose_executor.dc_state,
            )
            if check_up_result != JobResult.GOOD:
                services_status = await self.compose_executor.dc_state()
                raise ServicesUpError(
                    f"Can't check up services {services} for "
                    f"{self.health_policy.service_up_check_attempts * self.health_policy.service_up_check_delay_s}s"
                    f"\nServices status:\n {services_status.as_rich_text()}"
                ) from None

        await self.run_migration(
            [EventStage.AFTER_SERVICE_HEALTHY],
            services,
            self.compose_instance_files.env_config_instance,
            migrations
        )

    async def run(self):
        self.compose_instance_files = await self.generate_config_files()

        services_tiers = get_compose_services_dependency_tree(self.compose_instance_files.compose_files)
        self.logger.stage_info(
            Text('Starting services: ', style=Style.info)
            .append(Text(str(services_tiers), style=Style.good))
        )

        migrations = {}
        for service in self.compose_instance_files.env_config_instance.env:
            if service not in migrations:
                migrations[service] = []
            migrations[service] += self.compose_instance_files.env_config_instance.env[service].events_handlers
            migrations[service] += self.compose_instance_files.inline_migrations[service]

        all_services = [
            service
            for service_tier_pack in services_tiers
            for service in service_tier_pack
        ]

        await self.run_migration(
            [EventStage.BEFORE_ALL],
            all_services,
            self.compose_instance_files.env_config_instance,
            migrations
        )

        for service_tier_pack in services_tiers:
            await self.run_services_pack(service_tier_pack, migrations)

        await self.run_migration(
            [EventStage.AFTER_ALL],
            all_services,
            self.compose_instance_files.env_config_instance,
            migrations
        )

        if self.health_policy.wait_for_healthy_after_all:
            check_up_result = await wait_all_services_up(
                attempts=self.health_policy.service_up_check_attempts,
                delay_s=self.health_policy.service_up_check_delay_s,
                logger_func=self.logger.stage,
                get_compose_state=self.compose_executor.dc_state,
            )
            if check_up_result != JobResult.GOOD:
                services_status = await self.compose_executor.dc_state()
                raise ServicesUpError(
                    f"Can't up services {all_services} all together for "
                    f"{self.health_policy.service_up_check_attempts * self.health_policy.service_up_check_delay_s}s"
                    # TODO fix too verbose to file output?
                    # f"\nUp logs:\n {await self.logs(self.except_containers)}"
                    # f"\nServices logs:\n {await self.logs(services)}"
                    f"\nServices status:\n {services_status.as_rich_text()}"
                ) from None


    async def logs(self, services=None) -> str:
        job_result, log = await self.compose_executor.dc_logs(services, logs_param='')
        return log.decode('utf-8') if job_result == JobResult.GOOD else ''
