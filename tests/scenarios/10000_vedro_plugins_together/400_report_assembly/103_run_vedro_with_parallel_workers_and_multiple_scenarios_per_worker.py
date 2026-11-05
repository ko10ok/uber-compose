from contexts.compose_file import compose_file
from contexts.isolated_project import isolated_project
from contexts.no_docker_containers import no_docker_containers
from contexts.vedro_subprocess_project import vedro_subprocess_project
from helpers.env_vars import patch_env
from interfaces.vedro_cli import CliRunner
import vedro
import vedro.plugins.temp_keeper as temp_keeper


class Scenario(vedro.Scenario):
    subject = 'run vedro with parallel workers and multiple scenarios per worker'

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

    async def given_event_log(self):
        self.event_log = temp_keeper.create_tmp_dir(prefix='uc-events-') / 'events.log'
        patch_env({'UC_EVENT_LOG': str(self.event_log)})

    async def given_vedro_project_with_two_passing_scenarios(self):
        scenario_template = """
import vedro

from uber_compose import Environment
from uber_compose import Service


class Scenario(vedro.Scenario):
    subject = '{subject}'
    env = Environment(Service('s1'), description='{env_description}')

    def when_nothing_special_happens(self):
        self.result = 'ok'

    def then_it_should_just_pass(self):
        assert self.result == 'ok'
"""
        scenarios = {}
        for index in range(1, 5):
            scenarios[f'test_env_a_{index}.py'] = scenario_template.format(
                env_description='env-a', subject=f'passing env-a scenario {index}',
            )
        scenarios['test_env_b.py'] = scenario_template.format(
            env_description='env-b', subject='passing env-b scenario',
        )
        self.project_dir = vedro_subprocess_project(
            vedro_cfg=f"""
import os

import vedro

from vedro.core import Dispatcher
from vedro.core import Plugin
from vedro.core import PluginConfig
from vedro.events import ScenarioFailedEvent
from vedro.events import ScenarioPassedEvent
from vedro.events import ScenarioReportedEvent
from vedro.events import ScenarioRunEvent
from vedro.events import ScenarioSkippedEvent

from uber_compose import ComposeConfig
from uber_compose import DEFAULT_COMPOSE
from uber_compose import VedroUberCompose
from uber_compose import VedroUberComposeParallel


class EventRecorder(Plugin):
    def subscribe(self, dispatcher: Dispatcher) -> None:
        if os.environ.get('UC_WORKER_ID') is not None:
            return
        dispatcher.listen(ScenarioRunEvent, self.on_run)
        dispatcher.listen(ScenarioPassedEvent, self.on_passed)
        dispatcher.listen(ScenarioFailedEvent, self.on_failed)
        dispatcher.listen(ScenarioSkippedEvent, self.on_skipped)
        dispatcher.listen(ScenarioReportedEvent, self.on_reported)

    def _record(self, kind, result):
        with open(os.environ['UC_EVENT_LOG'], 'a') as file:
            file.write(f'{{kind}}|{{result.scenario.unique_id}}|{{result.scenario.subject}}\\n')

    def on_run(self, event):
        self._record('run', event.scenario_result)

    def on_passed(self, event):
        self._record('passed', event.scenario_result)

    def on_failed(self, event):
        self._record('failed', event.scenario_result)

    def on_skipped(self, event):
        self._record('skipped', event.scenario_result)

    def on_reported(self, event):
        self._record('reported', event.aggregated_result)


class Config(vedro.Config):
    class Plugins(vedro.Config.Plugins):
        class UberCompose(VedroUberCompose):
            enabled = True
            compose_cfgs = {{
                DEFAULT_COMPOSE: ComposeConfig(
                    compose_files="{self.compose_filename}",
                    env_parallelism={{"env-a": 2, "env-b": 1}},
                ),
            }}

        class UberComposeParallel(VedroUberComposeParallel):
            enabled = True

        class EventRecorder(PluginConfig):
            plugin = EventRecorder
            enabled = True
""",
            scenarios=scenarios,
        )

    async def when_vedro_is_run(self):
        self.run_result = await CliRunner().run_vedro(self.project_dir, args=['run', 'scenarios/'])

    async def then_it_should_exit_with_code_zero(self):
        assert self.run_result.returncode == 0, self.run_result.stdout + self.run_result.stderr

    async def and_it_should_report_all_scenarios_passed(self):
        assert '5 scenarios, 5 passed, 0 failed' in self.run_result.stdout

    async def and_events_of_each_scenario_should_be_atomic(self):
        events = []
        for line in self.event_log.read_text().splitlines():
            kind, unique_id, subject = line.split('|', 2)
            events.append({'kind': kind, 'subject': subject})

        current_subject = None
        finished_subjects = set()
        for event in events:
            if event['subject'] != current_subject:
                assert event['subject'] not in finished_subjects, \
                    f"non-atomic event stream for {event['subject']}"
                if current_subject is not None:
                    finished_subjects.add(current_subject)
                current_subject = event['subject']

        assert {event['subject'] for event in events} == {
            'passing env-a scenario 1',
            'passing env-a scenario 2',
            'passing env-a scenario 3',
            'passing env-a scenario 4',
            'passing env-b scenario',
        }

    async def and_each_scenario_should_have_complete_event_block(self):
        events = []
        for line in self.event_log.read_text().splitlines():
            kind, unique_id, subject = line.split('|', 2)
            events.append({'kind': kind, 'subject': subject})

        by_subject = {}
        for event in events:
            by_subject.setdefault(event['subject'], []).append(event['kind'])
        assert by_subject == {
            'passing env-a scenario 1': ['run', 'passed', 'reported'],
            'passing env-a scenario 2': ['run', 'passed', 'reported'],
            'passing env-a scenario 3': ['run', 'passed', 'reported'],
            'passing env-a scenario 4': ['run', 'passed', 'reported'],
            'passing env-b scenario': ['run', 'passed', 'reported'],
        }
