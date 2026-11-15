import os
from pathlib import Path
import re

from uber_compose.core.constants import DEFAULT_DOCKER_COMPOSE_FILES_AUTO_SCAN_PATTERN
from uber_compose.core.utils.compose_files import read_dc_file


def scan_for_compose_files(
    path: Path,
    dc_files_scan_depth: int = 1,
    files_pattern: str = DEFAULT_DOCKER_COMPOSE_FILES_AUTO_SCAN_PATTERN,
) -> list[str]:
    # TODO exclude paths with ENV
    compose_files = []
    for root, dirs, files in os.walk(path):
        if root.startswith(str(path)) and root.count('/') - str(path).count('/') < dc_files_scan_depth:
            for file in files:
                relative_path = str(Path(root) / file)[len(str(path)) + 1:]
                if not re.fullmatch(files_pattern, relative_path):
                    continue
                dc_file = read_dc_file(Path(root) / file)
                if 'services' in dc_file:
                    compose_files.append(relative_path)
    return list(sorted(compose_files))
