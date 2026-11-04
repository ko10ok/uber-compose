from pathlib import Path
from uuid import uuid4

import vedro

SCRATCH_ROOT = Path('/tmp/vedro-subprocess-projects')


def vedro_subprocess_project(vedro_cfg: str, scenarios: dict[str, str]) -> Path:
    """
    Materializes a standalone, disposable vedro project (its own vedro.cfg.py and
    scenario files) on disk, so it can be executed as a real `vedro run` subprocess
    - independent from the outer test runner process - to check the actual
    plugin/CLI integration surface rather than calling plugin internals in-process.

    `scenarios` maps a relative path under the project's `scenarios/` directory
    (e.g. 'test_up.py') to its file content.
    """
    project_dir = SCRATCH_ROOT / str(uuid4())
    (project_dir / 'scenarios').mkdir(parents=True, exist_ok=True)

    (project_dir / 'vedro.cfg.py').write_text(vedro_cfg)

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
