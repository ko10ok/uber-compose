from enum import Enum
from enum import auto
from typing import Dict
from typing import Iterator
from typing import List
from typing import NamedTuple

DEFAULT_ENV = 'DEFAULT'


class Environments:
    def __getitem__(self, item) -> 'Environment':
        return getattr(self, item)

    @classmethod
    def list_all(cls) -> list[str]:
        return [
            item
            for item in cls.__dict__
            if not item.startswith('__') or not item.startswith('_')
        ]


class AsIs:
    def __init__(self, value):
        self.value = value


class Env(Dict):
    ...


class StageName(NamedTuple):
    compose_name: str


class EventStage(Enum):
    BEFORE_ALL = StageName('before_all')
    BEFORE_SERVICE_START = StageName('before_start')
    AFTER_SERVICE_START = StageName('after_start')
    AFTER_SERVICE_HEALTHY = StageName('after_healthy')
    AFTER_ALL = StageName('after_all')

    @classmethod
    def get_all_stages(cls):
        return [
            cls.BEFORE_ALL,
            cls.BEFORE_SERVICE_START,
            cls.AFTER_SERVICE_START,
            cls.AFTER_SERVICE_HEALTHY,
            cls.AFTER_ALL,

        ]

    @classmethod
    def get_all_compose_stages(cls):
        return [stage.value.compose_name for stage in cls.get_all_stages()]

    @classmethod
    def get_compose_stage(cls, stage_name: str) -> 'EventStage':
        for stage in cls.get_all_stages():
            if stage.value.compose_name == stage_name:
                return stage
        assert False, 'No such stage: {}'.format(stage_name)


class Handler(NamedTuple):
    stage: EventStage
    cmd: str
    executor: str = None


class ServiceMode(Enum):
    ON = auto()
    OFF = auto()
    SINGLETON = auto()
    EXTERNAL = auto()


class Service(NamedTuple):
    name: str
    env: Env = Env()
    events_handlers: List[Handler] = []
    mode: ServiceMode = ServiceMode.ON

    def __eq__(self, other):
        return self.name == other.name

    def __repr__(self):
        return f'Service({self.name}, {self.mode})'

    def with_env(self, env: Env | dict):
        return Service(
            name=self.name,
            env=Env(self.env | env),
            events_handlers=self.events_handlers,
            mode=self.mode
        )

    def as_dict(self):
        return {
            'name': self.name,
            'env': dict(self.env),
        }


class OverridenService(NamedTuple):
    service: Service
    services_envs_fix: list[Service] | None = None

    def __eq__(self, other):
        if isinstance(other, str):
            return self.service.name == other
        if isinstance(other, OverridenService):
            return self.service.name == other.service.name
        if isinstance(other, Service):
            return self.service.name == other.name
        return False


def remove_dups(*services: Service) -> List[Service]:
    result_services = []
    for service in reversed(services):
        if service not in result_services:
            result_services += [service]

    return list(reversed(result_services))


class Environment:  # TODO rename Environment
    @classmethod
    def from_environment(cls, env: 'Environment', *services: Service, description='', services_override = None) -> 'Environment':
        # TODO duplicated services merging
        description = description or env._description
        services_overrides = []
        if services_override:
            services_overrides += services_override
        if env._services_override:
            services_overrides += env._services_override
        return Environment(*env._services, *services, description=description, services_override=services_overrides)

    def __init__(self, *services: Service | str, description='', services_override: List[OverridenService] | None = None):
        # TODO duplicated services merging
        self._description = description
        services = [
            Service(service) if isinstance(service, str) else service
            for service in services
        ]
        self._services = sorted(remove_dups(*services), key=lambda x: x.name)
        self._services_dict: dict[str, Service] = {
            item.name: item for item in self._services
        }
        self._services_override: List[OverridenService] = services_override or []

    def __str__(self) -> str:
        return self._description or f'Environment(<services: {",".join(service.name for service in self._services)})>'

    def __repr__(self):
        if self._description:
            return (f'Environment({self._description},'
                    f' <services: {",".join(service.name for service in self._services)}>)')
        return f'Environment(<services: {",".join(service.name for service in self._services)}>)'

    @property
    def description(self) -> str:
        return self._description

    def get_services(self) -> dict:
        return self._services_dict

    def get_overridden_services(self) -> List[OverridenService]:
        return self._services_override

    def get_overridden_services_names(self) -> List[OverridenService]:
        return [
            ovr_service.service.name
            for ovr_service in self._services_override
        ]

    def __getitem__(self, item) -> Service:
        return self._services_dict[item]

    def __iter__(self) -> Iterator[str]:
        return iter(self._services_dict)

    def isidentifier(self):
        return True

    def __eq__(self, other):
        return isinstance(other, Environment) and self._services == other._services

    def __hash__(self):
        return hash(str(self._services))

    def as_json(self) -> list[dict]:
        return [
            service.as_dict() for service in self._services
        ]

    def get_services_names(self):
        return [service.name for service in self._services]
