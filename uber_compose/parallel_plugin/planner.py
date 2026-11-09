from dataclasses import dataclass
from dataclasses import field
from pathlib import Path

from vedro.core import ScenarioScheduler

from uber_compose.env_description.env_types import DEFAULT_ENV_DESCRIPTION
from uber_compose.env_description.env_types import Environment
from uber_compose.helpers.workers_per_env import normalize_workers_per_env
from uber_compose.parallel_plugin.grouper import build_replica_execution_plan
from uber_compose.parallel_plugin.grouping import env_group_key_for
from uber_compose.parallel_plugin.grouping import scenario_env


@dataclass(frozen=True)
class PlanService:
    name: str
    mode: str = 'ON'
    env: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class PlanReplica:
    worker_id: int
    replica_index: int
    replicas_total: int
    namespace: str
    test_paths: tuple[str, ...] = ()


@dataclass(frozen=True)
class PlanEnvironment:
    name: str
    services: tuple[PlanService, ...] = ()
    test_paths: tuple[str, ...] = ()
    replicas: tuple[PlanReplica, ...] = ()


@dataclass(frozen=True)
class RunPlan:
    compose_config: str
    environments: tuple[PlanEnvironment, ...] = ()
    parallel: bool = False
    compose_files: str | None = None
    max_concurrent_envs: int = 1
    default_workers_per_env: int = 1
    uc_mt_enabled: bool = False
    ignored: tuple[str, ...] = ()


async def build_run_plan(
    scheduler: ScenarioScheduler,
    *,
    compose_config: str,
    compose_files: str | None,
    default_env: Environment | None,
    workers_per_env: dict | None,
    default_workers_per_env: int,
    max_concurrent_envs: int,
    uc_mt_enabled: bool,
    workers_per_env_override: int | None = None,
) -> RunPlan:
    grouped = await _group_scenarios(scheduler, default_env)
    if not grouped:
        return RunPlan(
            compose_config=compose_config,
            compose_files=compose_files,
            parallel=False,
            max_concurrent_envs=max_concurrent_envs,
            default_workers_per_env=default_workers_per_env,
            uc_mt_enabled=uc_mt_enabled,
        )

    normalized_workers = normalize_workers_per_env(workers_per_env)
    if uc_mt_enabled:
        replica_plan = build_replica_execution_plan(
            group_counts={key: len(item.scenarios) for key, item in grouped.items()},
            group_envs={key: item.display_env for key, item in grouped.items()},
            namespace_counts={
                key: _replicas_for_env(
                    item,
                    normalized_workers,
                    default_workers_per_env,
                    workers_per_env_override,
                )
                for key, item in grouped.items()
            },
            default_replicas=default_workers_per_env,
        )
        if replica_plan.workers_total > 1:
            return _parallel_run_plan(
                grouped,
                replica_plan,
                compose_config=compose_config,
                compose_files=compose_files,
                max_concurrent_envs=max_concurrent_envs,
                default_workers_per_env=default_workers_per_env,
            )

    return _sequential_run_plan(
        grouped,
        compose_config=compose_config,
        compose_files=compose_files,
        max_concurrent_envs=max_concurrent_envs,
        default_workers_per_env=default_workers_per_env,
        uc_mt_enabled=uc_mt_enabled,
    )


@dataclass
class _GroupedEnv:
    key: str
    name: str
    template: Environment | None
    display_env: Environment | None
    scenarios: list


async def _group_scenarios(scheduler: ScenarioScheduler, default_env: Environment | None) -> dict[str, _GroupedEnv]:
    grouped: dict[str, _GroupedEnv] = {}
    async for scenario in scheduler:
        if scenario.is_skipped():
            continue
        env = scenario_env(scenario)
        group_key = env_group_key_for(env)
        if group_key not in grouped:
            display_env = env or default_env
            grouped[group_key] = _GroupedEnv(
                key=group_key,
                name=_env_name(display_env),
                template=env,
                display_env=display_env,
                scenarios=[],
            )
        grouped[group_key].scenarios.append(scenario)
    return grouped


def _env_name(env: Environment | None) -> str:
    if env is None or not env.description:
        return DEFAULT_ENV_DESCRIPTION
    return env.description


def _replicas_for_env(
    item: _GroupedEnv,
    workers_per_env: dict[str, int] | None,
    default_workers_per_env: int,
    workers_per_env_override: int | None,
) -> int:
    if workers_per_env_override is not None:
        return max(workers_per_env_override, 1)
    if workers_per_env and item.name in workers_per_env:
        return max(workers_per_env[item.name], 1)
    return max(default_workers_per_env, 1)


def _parallel_run_plan(
    grouped: dict[str, _GroupedEnv],
    replica_plan,
    *,
    compose_config: str,
    compose_files: str | None,
    max_concurrent_envs: int,
    default_workers_per_env: int,
) -> RunPlan:
    environments = []
    for group_key, item in sorted(grouped.items(), key=lambda pair: pair[1].name):
        assignments = [
            assignment
            for assignment in replica_plan.assignments
            if group_key in assignment.groups
        ]
        replicas = tuple(
            PlanReplica(
                worker_id=assignment.worker_id,
                replica_index=assignment.replica_index,
                replicas_total=assignment.replicas_total,
                namespace=assignment.namespace_map[group_key],
                test_paths=_replica_test_paths(
                    item.scenarios,
                    assignment.replica_index,
                    assignment.replicas_total,
                ),
            )
            for assignment in assignments
        )
        environments.append(PlanEnvironment(
            name=item.name,
            services=_plan_services(item.display_env),
            replicas=replicas,
        ))

    return RunPlan(
        compose_config=compose_config,
        compose_files=compose_files,
        parallel=True,
        max_concurrent_envs=max_concurrent_envs,
        default_workers_per_env=default_workers_per_env,
        uc_mt_enabled=True,
        environments=tuple(environments),
    )


def _sequential_run_plan(
    grouped: dict[str, _GroupedEnv],
    *,
    compose_config: str,
    compose_files: str | None,
    max_concurrent_envs: int,
    default_workers_per_env: int,
    uc_mt_enabled: bool,
) -> RunPlan:
    environments = tuple(
        PlanEnvironment(
            name=item.name,
            services=_plan_services(item.display_env),
            test_paths=_test_paths(item.scenarios),
        )
        for _, item in sorted(grouped.items(), key=lambda pair: pair[1].name)
    )
    return RunPlan(
        compose_config=compose_config,
        compose_files=compose_files,
        parallel=False,
        max_concurrent_envs=max_concurrent_envs,
        default_workers_per_env=default_workers_per_env,
        uc_mt_enabled=uc_mt_enabled,
        environments=environments,
    )


def _replica_test_paths(scenarios: list, replica_index: int, replicas_total: int) -> tuple[str, ...]:
    ordered = sorted(scenarios, key=lambda scenario: str(scenario.unique_id))
    selected = [
        scenario
        for position, scenario in enumerate(ordered)
        if position % replicas_total == replica_index
    ]
    return _test_paths(selected)


def _test_paths(scenarios: list) -> tuple[str, ...]:
    return tuple(sorted({str(scenario.path) for scenario in scenarios}))


def _plan_services(env: Environment | None) -> tuple[PlanService, ...]:
    if env is None:
        return ()

    overridden = set(env.get_overridden_services_names())
    services = []
    for service_name, service in sorted(env.get_services().items()):
        if service_name in overridden:
            continue
        services.append(PlanService(
            name=service.name,
            mode=service.mode.name,
            env={str(key): str(value) for key, value in service.env.items()},
        ))
    return tuple(services)


_MODE_SUFFIX = {
    'SINGLETON': ' [singleton]',
    'OFF': ' [off]',
    'EXTERNAL': ' [external]',
}


def render_plan(plan: RunPlan, level: int = 0) -> str:
    if level < 0:
        raise ValueError('plan level must be >= 0')

    lines = [
        'uber-compose plan',
        'dry run: nothing will be started',
        '',
        f'compose config: {plan.compose_config}',
    ]
    if level >= 1 and plan.compose_files:
        lines.append(f'compose files: {plan.compose_files}')

    lines.append(f'lifecycle: {_render_lifecycle(plan)}')
    lines.append(f'infra: {_render_infra(plan)}')

    if level >= 1:
        lines.extend(_render_settings(plan))

    for environment in plan.environments:
        lines.append('')
        lines.extend(_render_environment(environment, plan, level))

    return '\n'.join(lines)


def _render_lifecycle(plan: RunPlan) -> str:
    names = [
        f'{environment.name}[{len(environment.replicas)}]'
        if plan.parallel else environment.name
        for environment in plan.environments
    ]
    if not names:
        return 'none'
    separator = ' || ' if plan.parallel or plan.max_concurrent_envs > 1 else ' -> '
    return separator.join(names)


def _render_infra(plan: RunPlan) -> str:
    workers_total = sum(len(environment.replicas) for environment in plan.environments)
    if plan.parallel and workers_total > 1:
        return f'root_orchestrator -> workers[{workers_total}]'
    return 'root_worker'


def _render_settings(plan: RunPlan) -> list[str]:
    lines = ['settings:']
    if plan.parallel:
        workers_per_env = ', '.join(
            f'{environment.name}[{len(environment.replicas)}]'
            for environment in plan.environments
        )
        if workers_per_env:
            lines.append(f'  workers_per_env: {workers_per_env}')
        lines.append(f'  default_workers_per_env: {plan.default_workers_per_env}')
    lines.append(f'  max_concurrent_envs: {plan.max_concurrent_envs}')
    lines.append(f'  --uc-mt: {"on" if plan.uc_mt_enabled else "off"}')

    ignored = list(plan.ignored)
    if plan.parallel and 'max_concurrent_envs (parallel run)' not in ignored:
        ignored.append('max_concurrent_envs (parallel run)')
    if ignored:
        lines.append(f'  ignored: {", ".join(ignored)}')
    return lines


def _render_environment(environment: PlanEnvironment, plan: RunPlan, level: int) -> list[str]:
    lines = [environment.name]
    if level == 0:
        lines.extend(_render_services_compact(environment))
    else:
        lines.extend(_render_services_detailed(environment))

    if plan.parallel:
        lines.append(f'  replicas[{len(environment.replicas)}]:')
        for replica in environment.replicas:
            lines.append(_render_replica(replica, environment, level))
    else:
        lines.append(_render_tests(environment.test_paths, level, indent='  '))
    return lines


def _render_services_compact(environment: PlanEnvironment) -> list[str]:
    services = ', '.join(
        f'{service.name}{_MODE_SUFFIX.get(service.mode, "")}'
        for service in environment.services
    )
    return [f'  services: {services}']


def _render_services_detailed(environment: PlanEnvironment) -> list[str]:
    lines = ['  services:']
    for service in environment.services:
        lines.append(f'    {service.name}{_MODE_SUFFIX.get(service.mode, "")}')
        if service.env:
            env = ', '.join(
                f'{key}={value}'
                for key, value in sorted(service.env.items())
            )
            lines.append(f'      env: {env}')
    return lines


def _render_replica(replica: PlanReplica, environment: PlanEnvironment, level: int) -> str:
    label = f'w{replica.worker_id}-{environment.name}[{replica.replica_index}]'
    parts = [f'    {label}']
    if level >= 1:
        parts.append(f'namespace: {replica.namespace}')
    parts.append(_render_tests(replica.test_paths, level, indent='', inline=True))
    return '  '.join(parts)


def _render_tests(test_paths: tuple[str, ...], level: int, indent: str, inline: bool = False) -> str:
    paths = tuple(test_paths)
    if level == 0:
        displayed = paths[:3]
        suffix = ', ...' if len(paths) > len(displayed) else ''
        rendered = ', '.join(_test_name(path, level) for path in displayed) + suffix
    else:
        rendered = ', '.join(_test_name(path, level) for path in paths)

    count = len(paths)
    if inline:
        return f'tests[{count}]: {rendered}'
    return f'{indent}tests[{count}]: {rendered}'


def _test_name(path: str, level: int) -> str:
    if level >= 2:
        return path
    return Path(path).name


__all__ = (
    'PlanEnvironment', 'PlanReplica', 'PlanService', 'RunPlan',
    'build_run_plan', 'render_plan',
)
