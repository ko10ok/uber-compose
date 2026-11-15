import os

import vedro


class Config(vedro.Config):
    COMPOSE_FILES_PATH = '/compose-files'
    ROOT_PATH = os.environ.get('HOST_PROJECT_ROOT_DIRECTORY')
