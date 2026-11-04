import os

import vedro
from vedro.plugins.director import RichReporter
from vedro_step_tracer import VedroStepTracer
import vedro_valera_validator as valera_validator


class Config(vedro.Config):
    class Plugins(vedro.Config.Plugins):
        class ValeraValidator(valera_validator.ValeraValidator):
            enabled = True

        class RichReporter(RichReporter):
            enabled = True
            scope_width = -1
            show_paths = 'failed'

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
