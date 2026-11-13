from datetime import datetime
import os
from pathlib import Path


def default_log_file_path() -> Path:
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    return Path.cwd() / 'logs' / 'startup' / f'uber-compose-{timestamp}-{os.getpid()}.log'


class Constants:
    def __init__(self,
                 docker_compose_files_scan_depth: int = 2,
                 cli_compose_util_override: str = None,
                 compose_project_name: str = None,
                 tmp_envs_path: str | Path = None,
                 in_docker_project_root_path: str | Path = None,
                 mounted_files_path: str | Path = None,
                 mounted_files_host_path: str | Path = None,
                 log_file_path: str | Path = None,
                 ):
        self.default_log_policy = os.environ.get('LOG_POLICY', 'DEFAULT')

        self.project: str = compose_project_name or os.environ.get('COMPOSE_PROJECT_NAME')
        self.compose_project_name = self.project
        assert self.compose_project_name, (
            'COMPOSE_PROJECT_NAME environment variable is not set: - COMPOSE_PROJECT_NAME=${PWD##*/}'
        )

        self.docker_host = os.environ.get('DOCKER_HOST', 'unix:///var/run/docker.sock')

        # inner directories
        self.non_stop_containers: list[str] = os.environ.get('NON_STOP_CONTAINERS', 'e2e,dockersock').split(',')
        self.tmp_envs_path: Path = Path(
            tmp_envs_path or os.environ.get('TMP_ENVS_DIRECTORY', '/tmp/uc-envs')
        )
        self.log_file_path: Path = Path(log_file_path or default_log_file_path())

        self.in_docker_project_root_path: Path = Path(
            in_docker_project_root_path or os.environ.get('PROJECT_ROOT_DIRECTORY', '/project')
        )

        self.host_project_root_directory: Path = Path(
            os.environ.get('HOST_PROJECT_ROOT_DIRECTORY', '__host_project_root__')
        )

        mounted_files_directory = mounted_files_path or os.environ.get('MOUNTED_FILES_DIRECTORY')
        if mounted_files_directory is None:
            self.mounted_files_path = Path.cwd() / 'e2e_mounted_files'
            self.mounted_files_host_path = (
                Path(mounted_files_host_path)
                if mounted_files_host_path is not None
                else self.mounted_files_path
            )
        else:
            mounted_files_path = Path(mounted_files_directory)
            if mounted_files_path.is_absolute():
                self.mounted_files_path = mounted_files_path
                self.mounted_files_host_path = (
                    Path(mounted_files_host_path)
                    if mounted_files_host_path is not None
                    else mounted_files_path
                )
            else:
                self.mounted_files_path = self.in_docker_project_root_path / mounted_files_path
                self.mounted_files_host_path = (
                    Path(mounted_files_host_path)
                    if mounted_files_host_path is not None
                    else self.host_project_root_directory / mounted_files_path
                )

        self.docker_compose_extra_exec_params = os.environ.get('DOCKER_COMPOSE_EXTRA_EXEC_PARAMS', '-T')

        self.docker_compose_files_scan_depth: int = int(
            os.environ.get('DOCKER_COMPOSE_FILES_SCAN_DEPTH', docker_compose_files_scan_depth)
        )

        self.ignore_pidof_unexistance: bool = bool(os.environ.get('IGNORE_PIDOF_UNEXISTANCE', 'True') == 'True')

        self.exec_pids_check_attempts_count: int = int(os.environ.get('EXEC_PIDS_CHECK_ATTEMPTS_COUNT', '150'))
        self.exec_pids_check_retry_delay: int = int(os.environ.get('EXEC_PIDS_CHECK_RETRY_DELAY', '1'))

        self.cli_compose_util_override: str = os.environ.get('CLI_COMPOSE_UTIL', cli_compose_util_override)
