import os
from pathlib import Path

from uber_compose.core.utils.compose_files import read_dc_file


def scan_for_compose_files(path: Path) -> list[str]:
    compose_files = []
    for root, dirs, files in os.walk(path):
        if len(root.split('/')) <= 4:
            for file in files:
                if file.endswith('.yml') or file.endswith('.yaml'):
                    dc_file = read_dc_file(Path(root) / file)
                    if 'services' in dc_file:
                        compose_files.append(str(Path(root) / file)[len(str(path)) + 1:])
    return list(sorted(compose_files))
