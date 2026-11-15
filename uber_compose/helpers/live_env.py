"""Cabina-based live environment values resolved for the current uber-compose env."""

from typing import Any
from typing import Callable

from cabina import FutureValue
from cabina import LazyEnvironment
from cabina.parsers import parse_as_is
from niltype import Nil

from uber_compose.core.sequence_run_types import DEFAULT_ENV_ID
from uber_compose.env_description.env_types import ServiceMode
from uber_compose.helpers.current_env import get_current_env_context
from uber_compose.helpers.parameterization import build_parameterization_placeholders
from uber_compose.helpers.parameterization import substitute_parameterization_placeholders


def current_environment_placeholders() -> dict[str, str]:
    """Build parameterization placeholders for the environment of the current thread."""
    context = get_current_env_context()
    namespace = context.namespace or context.env_id

    services_map = {}
    if context.env is not None:
        for service_name, service in context.env.get_services().items():
            if service.mode == ServiceMode.OFF:
                continue
            if service.mode == ServiceMode.SINGLETON or namespace == DEFAULT_ENV_ID:
                services_map[service_name] = service_name
            else:
                services_map[service_name] = f'{service_name}-{namespace}'

    return build_parameterization_placeholders(
        env_id=context.env_id,
        services_map=services_map,
        run_id=context.run_id,
        worker_id=context.worker_id,
        namespace=namespace,
    )


def resolve_current_placeholders(value: Any) -> Any:
    """Replace ``[[...]]`` placeholders in a value using the current environment context."""
    if not isinstance(value, str):
        return value
    return substitute_parameterization_placeholders(value, current_environment_placeholders())


class LiveValue(FutureValue):
    """A future value that is resolved on every access instead of being cached."""

    def get(self) -> Any:
        return self._accessor(*self._args, **self._kwargs)


class LiveEnvironment(LazyEnvironment):
    """Environment accessor whose values are re-read and re-substituted on every access."""

    def get(
        self,
        name: str,
        default: Any = Nil,
        parser: Callable[[str], Any] = parse_as_is,
    ) -> Any:
        raw_name = f'{self._prefix}{name}'
        if raw_name in self._environ:
            value = self._environ[raw_name]
            return parser(resolve_current_placeholders(value))

        if default is Nil:
            return super().get(name, default, parser)
        return resolve_current_placeholders(default)

    def raw(
        self,
        name: str,
        default: Any = Nil,
        parser: Callable[[str], Any] = parse_as_is,
    ) -> LiveValue:
        return LiveValue(self.get, name, default=default, parser=parser)

    def literal(self, value: Any) -> LiveValue:
        """Return a live value with placeholders substituted from the current environment."""
        return LiveValue(resolve_current_placeholders, value)


live_env = LiveEnvironment()


__all__ = (
    'LiveEnvironment', 'LiveValue', 'current_environment_placeholders', 'live_env',
    'resolve_current_placeholders',
)
