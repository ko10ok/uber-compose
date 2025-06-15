from pathlib import Path

import vedro


def _make_compose_file(filename: str, content: str):
    root = Path('/project')
    file_path = root / (Path(filename).parent)

    file_path.mkdir(parents=True, exist_ok=True)

    with open(root / filename, 'w') as file:
        file.write(content)

    vedro.defer(cleanup_compose_files)
    return filename


def cleanup_compose_files():
    for file in sorted(Path('/project').rglob('*'), key=lambda x: len(str(x)), reverse=True):
        if file.is_file():
            file.unlink(missing_ok=True)
        elif file.is_dir():
            file.rmdir()
    

def compose_file(filename: str, content: str):
    _make_compose_file(filename, content)
    vedro.defer(cleanup_compose_files)
    return filename
