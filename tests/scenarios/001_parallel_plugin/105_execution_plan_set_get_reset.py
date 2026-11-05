import vedro

from uber_compose import ExecutionPlan
from uber_compose import WorkerAssignment
from uber_compose import get_execution_plan
from uber_compose import reset_execution_plan
from uber_compose import set_execution_plan


class Scenario(vedro.Scenario):
    subject = 'execution plan can be published and read through worker api'

    async def given_published_execution_plan(self):
        reset_execution_plan()
        vedro.defer(reset_execution_plan)
        self.plan = ExecutionPlan(
            workers_total=2,
            assignments=(
                WorkerAssignment(
                    worker_id=0,
                    groups=('hash-a',),
                    namespace_map={'hash-a': 'w0-a1b2'},
                ),
                WorkerAssignment(
                    worker_id=1,
                    groups=('hash-b',),
                    namespace_map={'hash-b': 'w1-c3d4'},
                ),
            ),
        )

    async def when_plan_is_published(self):
        set_execution_plan(self.plan)

    async def then_it_should_be_readable(self):
        assert get_execution_plan() == self.plan

    async def and_it_should_resolve_namespace_map_per_worker(self):
        assert get_execution_plan().namespace_map_for(1) == {'hash-b': 'w1-c3d4'}

    async def and_it_should_resolve_env_id_by_group(self):
        assignment = get_execution_plan().assignment_for(0)
        assert assignment.env_id_for('hash-a') == 'w0-a1b2'
        assert assignment.env_id_for('unknown') is None

    async def when_plan_is_reset(self):
        reset_execution_plan()

    async def then_it_should_not_be_readable_anymore(self):
        assert get_execution_plan() is None
