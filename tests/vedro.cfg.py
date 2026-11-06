import os

import vedro
from vedro.core import Plugin
from vedro.core import PluginConfig
from vedro.events import ScenarioRunEvent
from vedro.plugins.director import RichReporter
import vedro.plugins.temp_keeper as temp_keeper
from vedro_step_tracer import VedroStepTracer
import vedro_valera_validator as valera_validator

from uber_compose import VedroUberComposeParallel
from uber_compose.helpers.current_env import get_current_env_context
from uber_compose.helpers.current_env import reset_current_env_id
from uber_compose.helpers.current_env import set_current_env_context

UC_WORKER_ENV = (
    'UC_WORKER_ID',
    'UC_WORKERS_TOTAL',
    'UC_WORKER_GROUPS',
    'UC_NAMESPACE_MAP',
    'UC_WORKER_REPLICA_INDEX',
    'UC_ENV_REPLICAS_TOTAL',
)


# Prevent the outer parallel worker's UC_* env and current-env context from leaking into scenarios.
class ScenarioWorkerEnvGuardPlugin(Plugin):
    def subscribe(self, dispatcher):
        dispatcher.listen(ScenarioRunEvent, self.on_scenario_run)

    def on_scenario_run(self, event):
        saved = {
            name: os.environ.pop(name)
            for name in UC_WORKER_ENV
            if name in os.environ
        }
        saved_context = get_current_env_context()
        reset_current_env_id()
        vedro.defer(self._restore, saved, saved_context)

    def _restore(self, saved, saved_context):
        os.environ.update(saved)
        set_current_env_context(saved_context)


class ScenarioWorkerEnvGuard(PluginConfig):
    plugin = ScenarioWorkerEnvGuardPlugin
    enabled = True


class Config(vedro.Config):
    class Plugins(vedro.Config.Plugins):
        class ValeraValidator(valera_validator.ValeraValidator):
            enabled = True

        class TempKeeper(temp_keeper.TempKeeper):
            enabled = True

        class ScenarioWorkerEnvGuard(ScenarioWorkerEnvGuard):
            enabled = True

        class UberComposeParallel(VedroUberComposeParallel):
            enabled = True

        class RichReporter(RichReporter):
            enabled = True
            scope_width = -1
            show_paths = 'failed'
            show_captured_output_limit = 0

        class StepTracer(VedroStepTracer):
            enabled = True
            target_dirs = ['helpers', 'contexts', 'interfaces']
            attach_artifacts = True
            print_to_stdout = False
            save_to_dir = True
            output_dir = 'logs/traces'
            host_project_root_directory = os.environ.get(
                'HOST_PROJECT_ROOT_DIRECTORY', '',
            ).removesuffix('/mnt/project')
