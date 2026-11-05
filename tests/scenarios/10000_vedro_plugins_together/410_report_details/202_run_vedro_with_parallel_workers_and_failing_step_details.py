import json

from contexts.compose_file import compose_file
from contexts.isolated_project import isolated_project
from contexts.no_docker_containers import no_docker_containers
from contexts.vedro_subprocess_project import vedro_subprocess_project
from helpers.env_vars import patch_env
from interfaces.vedro_cli import CliRunner
import vedro
import vedro.plugins.temp_keeper as temp_keeper


class Scenario(vedro.Scenario):
    subject = 'run vedro with parallel workers and failing step details in the report'

    async def given_no_docker_containers(self):
        no_docker_containers()

    async def given_isolated_project(self):
        self.project = isolated_project()
        self.compose_filename = 'docker-compose.yaml'
        compose_file(
            self.compose_filename,
            content="""
version: "3"

services:
  s1:
    image: busybox:stable
    command: 'sh -c "trap : TERM INT; sleep 604800; wait"'
"""
        )

    async def given_report_details_file(self):
        self.details_file = temp_keeper.create_tmp_dir(prefix='uc-details-') / 'details.jsonl'
        patch_env({'UC_REPORT_DETAILS': str(self.details_file)})

    async def given_vedro_project_with_artifacts_recorder(self):
        self.project_dir = vedro_subprocess_project(
            vedro_cfg=f"""
import json
import os

import vedro

from vedro.core import Dispatcher
from vedro.core import FileArtifact
from vedro.core import MemoryArtifact
from vedro.core import Plugin
from vedro.core import PluginConfig
from vedro.events import ScenarioPassedEvent
from vedro.events import ScenarioReportedEvent
from vedro.events import StepPassedEvent

from uber_compose import ComposeConfig
from uber_compose import DEFAULT_COMPOSE
from uber_compose import VedroUberCompose
from uber_compose import VedroUberComposeParallel


def artifact_to_dict(artifact):
    if isinstance(artifact, MemoryArtifact):
        return {{
            'kind': 'memory',
            'name': artifact.name,
            'mime': artifact.mime_type,
            'data': artifact.data.decode('utf-8', errors='replace'),
        }}
    if isinstance(artifact, FileArtifact):
        return {{
            'kind': 'file',
            'name': artifact.name,
            'mime': artifact.mime_type,
            'path': str(artifact.path),
        }}
    return {{'kind': type(artifact).__name__}}


class WorkerArtifactAttacher(Plugin):
    def subscribe(self, dispatcher: Dispatcher) -> None:
        if os.environ.get('UC_WORKER_ID') is None:
            return
        dispatcher.listen(ScenarioPassedEvent, self.on_scenario_passed)
        dispatcher.listen(StepPassedEvent, self.on_step_passed)

    def on_scenario_passed(self, event):
        event.scenario_result.attach(
            MemoryArtifact('scenario-log', 'text/plain', b'scenario artifact')
        )

    def on_step_passed(self, event):
        event.step_result.attach(
            MemoryArtifact('step-log', 'text/plain', b'step artifact')
        )


class DetailsRecorder(Plugin):
    def subscribe(self, dispatcher: Dispatcher) -> None:
        if os.environ.get('UC_WORKER_ID') is not None:
            return
        dispatcher.listen(ScenarioReportedEvent, self.on_reported)

    def on_reported(self, event):
        result = event.aggregated_result
        payload = {{
            'subject': result.scenario.subject,
            'status': result.status.value,
            'steps': [
                {{
                    'name': step.step.name,
                    'status': step.status.value,
                    'error': None if step.exc_info is None else {{
                        'type': step.exc_info.type.__name__,
                        'message': str(step.exc_info.value),
                    }},
                    'artifacts': [artifact_to_dict(item) for item in step.artifacts],
                }}
                for step in result.step_results
            ],
            'artifacts': [artifact_to_dict(item) for item in result.artifacts],
        }}
        with open(os.environ['UC_REPORT_DETAILS'], 'a') as file:
            file.write(json.dumps(payload) + '\\n')


class Config(vedro.Config):
    class Plugins(vedro.Config.Plugins):
        class UberCompose(VedroUberCompose):
            enabled = True
            compose_cfgs = {{
                DEFAULT_COMPOSE: ComposeConfig(
                    compose_files="{self.compose_filename}",
                ),
            }}

        class UberComposeParallel(VedroUberComposeParallel):
            enabled = True

        class WorkerArtifactAttacher(PluginConfig):
            plugin = WorkerArtifactAttacher
            enabled = True

        class DetailsRecorder(PluginConfig):
            plugin = DetailsRecorder
            enabled = True
""",
            scenarios={
                'test_env_a.py': """
import vedro

from uber_compose import Environment
from uber_compose import Service


class Scenario(vedro.Scenario):
    subject = 'scenario with a failing step'
    env = Environment(Service('s1'), description='env-a')

    def when_first_step(self):
        self.result = 'broken'

    def then_second_step(self):
        assert self.result == 'ok', 'expected ok result'
""",
                'test_env_b.py': """
import vedro

from uber_compose import Environment
from uber_compose import Service


class Scenario(vedro.Scenario):
    subject = 'passing scenario in another env'
    env = Environment(Service('s1'), description='env-b')

    def when_nothing_special_happens(self):
        self.result = 'ok'

    def then_it_should_just_pass(self):
        assert self.result == 'ok'
"""
            },
        )

    async def when_vedro_is_run(self):
        self.run_result = await CliRunner().run_vedro(
            self.project_dir, args=['run', 'scenarios/', '--uc-mt']
        )

    async def then_it_should_exit_with_failure_code(self):
        assert self.run_result.returncode != 0, self.run_result.stdout + self.run_result.stderr

    async def and_it_should_report_failing_step_with_error(self):
        details = [
            json.loads(line)
            for line in self.details_file.read_text().splitlines()
        ]
        details = [detail for detail in details if detail['subject'] == 'scenario with a failing step']
        assert len(details) == 1
        assert details[0]['status'] == 'FAILED'
        assert [step['name'] for step in details[0]['steps']] == [
            'when_first_step',
            'then_second_step',
        ]
        assert [step['status'] for step in details[0]['steps']] == ['PASSED', 'FAILED']
        assert details[0]['steps'][1]['error'] == {
            'type': 'AssertionError',
            'message': 'expected ok result',
        }
        assert details[0]['steps'][0]['error'] is None
