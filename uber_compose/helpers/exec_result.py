from dataclasses import dataclass
from typing import NamedTuple


class ExecResult(NamedTuple):
    stdout: bytes
    cmd: str

    def __str__(self):
        return (f'ExecResult('
                f'  cmd={self.cmd}, '
                f'  stdout={self.stdout}, '
                f')')


class ExecTimeout(NamedTuple):
    stdout: bytes
    cmd: str

    def __str__(self):
        return (f'ExecTimeout('
                f'  cmd={self.cmd}, '
                f'  stdout={self.stdout}, '
                f')')
