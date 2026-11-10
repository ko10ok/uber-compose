from pathlib import Path


class MountedFileNotFoundError(FileNotFoundError):
    def __init__(
        self,
        relative_path: str | Path,
        env_id: str,
        searched_path: Path,
        mounted_files_dir: Path,
        project_root: Path,
    ):
        if searched_path.is_dir():
            reason = 'path exists but is a directory'
        else:
            reason = 'file does not exist'

        super().__init__(
            f'Mounted file not found: {str(relative_path)!r} ({reason}).\n'
            f'Env: {env_id}\n'
            f'Searched in test container: {searched_path}\n'
            f'Container project root: {project_root}\n'
            f'Mounted files root in container: {mounted_files_dir}\n'
            f'Hint: check mounted_files in the service and that this env was started.'
        )
