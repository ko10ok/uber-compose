import os
from pathlib import Path


class Constants:
    def __init__(self):
        self.default_log_policy = os.environ.get('LOG_POLICY', 'DEFAULT')

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

        # TODO remake timeouts and retries:
        # TODO call it pre migration checks
        self.docker_compose_extra_exec_params = os.environ.get('DOCKER_COMPOSE_EXTRA_EXEC_PARAMS', '-T')
