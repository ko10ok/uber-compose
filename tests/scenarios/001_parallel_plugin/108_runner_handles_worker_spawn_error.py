import asyncio
from unittest.mock import patch

import vedro
from vedro.core import Dispatcher

from uber_compose import WorkerAssignment
from uber_compose.parallel_plugin.runner import ParallelScenarioRunner


class Scenario(vedro.Scenario):
    subject = 'parallel runner handles a worker spawn failure without crashing'

    async def given_runner_and_worker_assignment(self):
        self.runner = ParallelScenarioRunner(dispatcher=Dispatcher(), grouping_key=lambda scenario: '')
        self.assignment = WorkerAssignment(worker_id=0, groups=('hash-a',))
        self.fire_lock = asyncio.Lock()

    async def when_worker_process_cannot_be_spawned(self):
        with patch('asyncio.create_subprocess_exec', side_effect=FileNotFoundError('no python')):
            self.worker_run = await self.runner._run_worker(
                assignment=self.assignment,
                workers_total=1,
                scenario_paths=['scenario.py'],
                scenarios={},
                aggregated={},
                fire_lock=self.fire_lock,
            )

    async def then_it_should_return_spawn_error_instead_of_raising(self):
        assert self.worker_run['worker_id'] == 0
        assert self.worker_run['spawn_error'] == 'no python'
        assert self.worker_run['returncode'] is None

    async def and_failure_message_should_describe_the_spawn_error(self):
        message = self.runner._worker_failure_message([self.worker_run])
        assert 'failed to start' in message
        assert 'no python' in message
