from pathlib import Path
from uuid import uuid4

import vedro

SCRATCH_ROOT = Path('/tmp/vedro-subprocess-projects')
BASE_CONFIG_PATH = Path(__file__).resolve().parents[1] / 'vedro.cfg.py'
BASE_CONFIG_NAME = '_uc_base_vedro_cfg.py'

_CHILD_CONFIG_PREAMBLE = f'''import os
from pathlib import Path

from uber_compose.helpers.current_env import increment_run_depth

_project_dir = str(Path(__file__).resolve().parent)
if os.environ.get('UC_CHILD_PROJECT_DIR') != _project_dir:
    increment_run_depth()
    os.environ['UC_CHILD_PROJECT_DIR'] = _project_dir

from {BASE_CONFIG_NAME.removesuffix('.py')} import Config as _BaseConfig
'''


def _render_vedro_cfg(vedro_cfg: str) -> str:
    rendered = vedro_cfg.replace(
        'class Config(vedro.Config):',
        'class Config(_BaseConfig):',
        1,
    ).replace(
        'class Plugins(vedro.Config.Plugins):',
        'class Plugins(_BaseConfig.Plugins):',
        1,
    )
    if 'class Config(_BaseConfig):' not in rendered:
        raise ValueError('vedro_cfg must define class Config(vedro.Config)')
    if 'class Plugins(_BaseConfig.Plugins):' not in rendered:
        raise ValueError('vedro_cfg must define class Plugins(vedro.Config.Plugins)')
    return f'{_CHILD_CONFIG_PREAMBLE}\n{rendered}'


def vedro_subprocess_project(vedro_cfg: str, scenarios: dict[str, str]) -> Path:
    """
    Materializes a standalone, disposable vedro project (its own vedro.cfg.py and
    scenario files) on disk, so it can be executed as a real `vedro run` subprocess
    - independent from the outer test runner process - to check the actual
    plugin/CLI integration surface rather than calling plugin internals in-process.

    The generated config is based on the project base vedro config and applies the
    provided config as overrides, so the child project gets all base plugins and
    only explicitly redefined plugins/options differ.

    `scenarios` maps a relative path under the project's `scenarios/` directory
    (e.g. 'test_up.py') to its file content.
    """
    project_dir = SCRATCH_ROOT / str(uuid4())
    (project_dir / 'scenarios').mkdir(parents=True, exist_ok=True)

    (project_dir / BASE_CONFIG_NAME).write_text(BASE_CONFIG_PATH.read_text())
    (project_dir / 'vedro.cfg.py').write_text(_render_vedro_cfg(vedro_cfg))

    for relative_path, content in scenarios.items():
        scenario_path = project_dir / 'scenarios' / relative_path
        scenario_path.parent.mkdir(parents=True, exist_ok=True)
        scenario_path.write_text(content)

    vedro.defer(_cleanup_project, project_dir)
    return project_dir


def _cleanup_project(project_dir: Path) -> None:
    for file in sorted(project_dir.rglob('*'), key=lambda x: len(str(x)), reverse=True):
        if file.is_file():
            file.unlink(missing_ok=True)
        elif file.is_dir():
            file.rmdir()
    if project_dir.exists():
        project_dir.rmdir()
