from enum import Enum
from enum import auto


class JobResult(Enum):
    GOOD = auto()
    BAD = auto()


class OperationError(Exception):
    def __init__(self, log: str):
        super().__init__(log)
        self.log = log

    def __eq__(self, other):
        return other == JobResult.BAD

    def __repr__(self):
        return f'Operation finished unsuccessful:\n{self.log}'
