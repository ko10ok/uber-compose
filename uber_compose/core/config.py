import os
from pathlib import Path


class Config:
    def __init__(self):
        self.project: str = os.environ.get('COMPOSE_PROJECT_NAME')
        self.compose_project_name = os.environ.get('COMPOSE_PROJECT_NAME')
        assert self.compose_project_name, 'COMPOSE_PROJECT_NAME environment variable is not set: - COMPOSE_PROJECT_NAME=${PWD##*/}'

        self.docker_host = os.environ.get('DOCKER_HOST', 'unix:///var/run/docker.sock')

        # inner dirrectories
        self.non_stop_containers: list[str] = os.environ.get('NON_STOP_CONTAINERS', 'e2e,dockersock').split(',')
        self.tmp_envs_path: Path = Path(os.environ.get('TMP_ENVS_DIRECTORY', '/tmp-envs'))
        self.in_docker_project_root_path: Path = Path(os.environ.get('PROJECT_ROOT_DIRECTORY', '/project'))

        # outer directories for output???
        self.host_project_root_directory: Path = Path(
            os.environ.get('HOST_PROJECT_ROOT_DIRECTORY', '__host_project_root__')
        )

        # TODO remake debug verbosity levels:
        self.debug_docker_compose_commands = bool(os.environ.get('DEBUG_DOCKER_COMPOSE_OUTPUT_TO_STDOUT', False))
        self.verbose_docker_compose_commands = bool(os.environ.get('VERBOSE_DOCKER_COMPOSE_OUTPUT_TO_STDOUT', True))
        self.verbose_docker_compose_ps_commands = bool(
            os.environ.get('VERBOSE_DOCKER_COMPOSE_PS_OUTPUT_TO_STDOUT', False)
        )
        # TODO remake timeouts and retries:
        # TODO call it pre migration checks
        self.service_up_check_attempts = int(os.environ.get('PRE_MIGRATIONS_CHECK_SERVICE_UP_ATTEMPTS', 100))
        self.service_up_check_delay = int(os.environ.get('PRE_MIGRATIONS_CHECK_SERVICE_UP_CHECK_DELAY', 3))
        self.docker_compose_extra_exec_params = os.environ.get('DOCKER_COMPOSE_EXTRA_EXEC_PARAMS', '-T')
