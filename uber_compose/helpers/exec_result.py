from typing import NamedTuple


class TerminatedByCondition(int):
    """Exit code marker for a process stopped because a wait condition was met.

    It behaves like an int exit code but is always truthy: the termination was
    intentional, so even a zero code must not look like an error or a missing
    result.
    """

    def __new__(cls, exit_code: int = 0):
        return super().__new__(cls, exit_code)

    def __repr__(self) -> str:
        return f'{type(self).__name__}({int(self)})'

    def __bool__(self) -> bool:
        return True

    def __eq__(self, other) -> bool:
        if isinstance(other, int):
            return int(self) == int(other)
        return NotImplemented

    def __hash__(self) -> int:
        return hash(int(self))


class ExecResult(NamedTuple):
    stdout: bytes
    cmd: str
    exit_code: int | None = None

    def __str__(self):
        return (f'ExecResult('
                f'  cmd={self.cmd}, '
                f'  stdout={self.stdout}, '
                f'  exit_code={self.exit_code}, '
                f')')


class ExecTimeout(NamedTuple):
    stdout: bytes
    cmd: str
    exit_code: int | None = None

    def __str__(self):
        return (f'ExecTimeout('
                f'  cmd={self.cmd}, '
                f'  stdout={self.stdout}, '
                f'  exit_code={self.exit_code}, '
                f')')
