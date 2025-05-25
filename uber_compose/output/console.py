import enum
from enum import auto

from rich.console import Console

CONSOLE = Console(highlight=False, force_terminal=True, markup=False, soft_wrap=True)

#
# # stream can be file or sys.stdout/sys.stderr
# class Stream(enum):
#     FILE = auto()
#     STDOUT = auto()
#
#
# class ConsoleOutput:
#     def __init__(self, stream: Stream):
#         self.stream = stream
#
#     @staticmethod
#     def print(*args, **kwargs):
#         console = Console(highlight=False, force_terminal=True, markup=False, soft_wrap=True)
#         return console.print
