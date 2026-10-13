import inspect
from collections import defaultdict
from enum import Enum
from typing import Any
from typing import Callable


class UberComposeEvent(Enum):
    AFTER_UP = 'after_up'
    AFTER_UPDATED_ENV_UP = 'after_updated_env_up'


class HooksRegistry:
    def __init__(self) -> None:
        self._hooks: dict[UberComposeEvent, list[tuple[Callable[..., Any], tuple, dict]]] = defaultdict(list)

    def on(self, event: UberComposeEvent, func: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        self._hooks[event].append((func, args, kwargs))

    async def run(self, event: UberComposeEvent) -> None:
        for func, args, kwargs in self._hooks[event]:
            result = func(*args, **kwargs)
            if inspect.isawaitable(result):
                await result
