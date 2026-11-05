from contextvars import ContextVar
import os
from pathlib import Path
from typing import NamedTuple
from uuid import uuid4

import vedro
import vedro.plugins.temp_keeper as temp_keeper

from uber_compose.core.constants import Constants


class AppliedEnvPatch(NamedTuple):
    previous: dict[str, str | None]


class IsolatedProject(NamedTuple):
    project_name: str
    project_root: Path
    tmp_envs_path: Path
    applied_env: AppliedEnvPatch


_current_project: ContextVar[IsolatedProject | None] = ContextVar(
    'test_isolated_project', default=None,
)


def isolated_project() -> IsolatedProject:
    current_project = _current_project.get()
    if current_project is not None:
        rollback_isolated_project(current_project)

    project_root = temp_keeper.create_tmp_dir(prefix='uc-project-')
    tmp_envs_path = temp_keeper.create_tmp_dir(prefix='uc-envs-')
    applied_env = apply_test_env_vars({
        'COMPOSE_PROJECT_NAME': f'uc-test-{uuid4().hex}',
        'PROJECT_ROOT_DIRECTORY': str(project_root),
        'TMP_ENVS_DIRECTORY': str(tmp_envs_path),
    })

    project = IsolatedProject(
        project_name=os.environ['COMPOSE_PROJECT_NAME'],
        project_root=project_root,
        tmp_envs_path=tmp_envs_path,
        applied_env=applied_env,
    )
    _reset_singletons()

    _current_project.set(project)
    vedro.defer(rollback_isolated_project, project)
    return project


def isolated_constants(project: IsolatedProject, **overrides) -> Constants:
    constants_kwargs = {
        'compose_project_name': project.project_name,
        'tmp_envs_path': project.tmp_envs_path,
        'in_docker_project_root_path': project.project_root,
    }
    constants_kwargs.update(overrides)
    return Constants(**constants_kwargs)


def get_isolated_project() -> IsolatedProject:
    project = _current_project.get()
    assert project is not None, (
        'Isolated project is not started. Call isolated_project() in the scenario setup.'
    )
    return project


def apply_test_env_vars(env_patch: dict[str, str]) -> AppliedEnvPatch:
    applied = AppliedEnvPatch(
        previous={key: os.environ.get(key) for key in env_patch},
    )
    os.environ.update(env_patch)
    return applied


def rollback_test_env_vars(applied_env: AppliedEnvPatch) -> None:
    for key, value in applied_env.previous.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def rollback_isolated_project(project: IsolatedProject) -> None:
    rollback_test_env_vars(project.applied_env)
    if _current_project.get() is project:
        _current_project.set(None)


def _reset_singletons() -> None:
    from uber_compose.helpers.singleton import SingletonMeta
    from uber_compose.uber_compose import TheUberCompose

    SingletonMeta._instances.pop(TheUberCompose, None)
