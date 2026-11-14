from helpers.vedro.scenario import make_scenario
import vedro
from vedro.core import MonotonicScenarioScheduler

from uber_compose import Environment
from uber_compose import ExecutionPlan
from uber_compose import Service
from uber_compose import build_execution_plan
from uber_compose import build_execution_plan_from_scheduler
from uber_compose import env_group_key
from uber_compose.parallel_plugin.grouper import assign_groups_to_workers


class Scenario(vedro.Scenario):
    subject = 'grouper assigns env groups to workers balancing scenario counts'

    async def given_group_counts(self):
        self.group_counts = {'hash-a': 5, 'hash-b': 1, 'hash-c': 1}

    async def then_groups_should_be_balanced_across_workers(self):
        assert assign_groups_to_workers(self.group_counts, 2) == [
            ['hash-a'],
            ['hash-b', 'hash-c'],
        ]

    async def then_execution_plan_should_contain_assignments(self):
        plan = build_execution_plan(self.group_counts, 2)
        assert isinstance(plan, ExecutionPlan)
        assert plan.workers_total == 2
        assert plan.assignment_for(0).groups == ('hash-a',)
        assert plan.assignment_for(1).groups == ('hash-b', 'hash-c')

    async def then_execution_plan_should_carry_namespace_map_for_known_groups(self):
        plan = build_execution_plan(
            self.group_counts,
            2,
            namespace_map={'hash-a': 'w0-a1b2', 'hash-b': 'w1-c3d4'},
        )
        assert plan.namespace_map_for(0) == {'hash-a': 'w0-a1b2'}
        assert plan.namespace_map_for(1) == {'hash-b': 'w1-c3d4'}
        assert plan.assignment_for(1).env_id_for('hash-c') is None

    async def then_single_worker_should_get_all_groups(self):
        plan = build_execution_plan(self.group_counts, 1)
        assert plan.assignment_for(0).groups == ('hash-a', 'hash-b', 'hash-c')

    async def then_scheduler_plan_should_match_group_counts(self):
        env_a = Environment(Service('s1'), description='env-a')
        env_b = Environment(Service('s1'), description='env-b')
        scheduler = MonotonicScenarioScheduler([
            make_scenario(env=env_a),
            make_scenario(env=env_a),
            make_scenario(env=env_b),
        ])
        plan = await build_execution_plan_from_scheduler(scheduler, 2, env_group_key)
        groups = {
            group
            for assignment in plan.assignments
            for group in assignment.groups
        }
        expected = {
            env_group_key(make_scenario(env=env_a)),
            env_group_key(make_scenario(env=env_b)),
        }
        assert groups == expected
