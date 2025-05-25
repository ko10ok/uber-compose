from uuid import uuid4

from rich.text import Text

from uber_compose.core.config import Config
from uber_compose.core.docker_compose import ComposeInstance
from uber_compose.core.docker_compose_shell.interface import ComposeShellInterface
from uber_compose.core.sequence_run_types import EMPTY_ID
from uber_compose.core.system_docker_compose import SystemDockerCompose
from uber_compose.core.utils.compose_instance_cfg import get_new_env_id
from uber_compose.env_description.env_types import Environment
from uber_compose.output.console import CONSOLE
from uber_compose.output.styles import Style


class UberCompose:
    def __init__(self):
        self.inner_project_root = Config().in_docker_project_root_path
        self.system_docker_compose = SystemDockerCompose(self.inner_project_root)

    async def up(self,
                 config_template: Environment | None = None,
                 compose_files: str | None = None,
                 force_restart: bool = False,
                 release_id: str | None = None,
                 parallelism_limit: int = 1,
                 ) -> str:

        if not compose_files:
            compose_files = self.system_docker_compose.get_default_compose_files()

        if not config_template:
            config_template = self.system_docker_compose.get_default_environment()

        existing_env_id = await self.system_docker_compose.get_env_id_for(config_template, compose_files)
        if existing_env_id and not force_restart:
            CONSOLE.print(Text(
                'Found suitable ready env: ', style=Style.info
            ).append(Text(existing_env_id, style=Style.mark)))
            return existing_env_id

        CONSOLE.print(Text('Starting new environment', style=Style.info))

        new_env_id = get_new_env_id()
        if release_id is None:
            release_id = str(uuid4())

        if parallelism_limit == 1:
            CONSOLE.print(f'Using default service names with {parallelism_limit=}')
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
        )

        await compose_instance.run()

        # TODO check if ready by state checking

        CONSOLE.print(Text(f'New environment started'))

        return new_env_id
