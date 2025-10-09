import os
from pathlib import Path


class Constants:
    def __init__(self,
                 docker_compose_files_scan_depth: int = 2,
                 cli_compose_util_override: str = None,
                 ):
        self.default_log_policy = os.environ.get('LOG_POLICY', 'DEFAULT')

        self.project: str = os.environ.get('COMPOSE_PROJECT_NAME')
        self.compose_project_name = os.environ.get('COMPOSE_PROJECT_NAME')
        assert self.compose_project_name, 'COMPOSE_PROJECT_NAME environment variable is not set: - COMPOSE_PROJECT_NAME=${PWD##*/}'

        self.docker_host = os.environ.get('DOCKER_HOST', 'unix:///var/run/docker.sock')

        # inner directories
        self.non_stop_containers: list[str] = os.environ.get('NON_STOP_CONTAINERS', 'e2e,dockersock').split(',')
        self.tmp_envs_path: Path = Path(os.environ.get('TMP_ENVS_DIRECTORY', '/tmp/uc-envs'))
        self.in_docker_project_root_path: Path = Path(os.environ.get('PROJECT_ROOT_DIRECTORY', '/project'))

        self.host_project_root_directory: Path = Path(
            os.environ.get('HOST_PROJECT_ROOT_DIRECTORY', '__host_project_root__')
        )

        self.docker_compose_extra_exec_params = os.environ.get('DOCKER_COMPOSE_EXTRA_EXEC_PARAMS', '-T')

        self.docker_compose_files_scan_depth: int = int(
            os.environ.get('DOCKER_COMPOSE_FILES_SCAN_DEPTH', docker_compose_files_scan_depth)
        )

        self.ignore_pidof_unexistance: bool = bool(os.environ.get('IGNORE_PIDOF_UNEXISTANCE', 'True') == 'True')

        self.exec_pids_check_attempts_count: int = int(os.environ.get('EXEC_PIDS_CHECK_ATTEMPTS_COUNT', '150'))
        self.exec_pids_check_retry_delay: int = int(os.environ.get('EXEC_PIDS_CHECK_RETRY_DELAY', '1'))

        self.cli_compose_util_override: str = os.environ.get('CLI_COMPOSE_UTIL', cli_compose_util_override)
