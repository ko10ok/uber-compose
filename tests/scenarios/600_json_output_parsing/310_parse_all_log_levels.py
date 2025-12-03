import vedro
from d42 import schema

from uber_compose.vedro_plugin.base_structures.common_json_cli import JsonParser, LogLevels


class Scenario(vedro.Scenario):
    subject = 'parse_output_to_json with all log levels'

    def given_json_parser(self):
        self.parser = JsonParser()

    def given_logs_with_all_levels(self):
        self.logs = b'''{"level": "trace", "msg": "Trace message"}
{"level": "debug", "msg": "Debug message"}
{"level": "info", "msg": "Info message"}
{"level": "warning", "msg": "Warning message"}
{"level": "error", "msg": "Error message"}
{"level": "fatal", "msg": "Fatal message"}
{"level": "panic", "msg": "Panic message"}'''

    def when_user_parses_logs(self):
        self.stdout, self.stderr = self.parser.parse_output_to_json(self.logs)

    def then_stdout_should_contain_all_levels(self):
        # full_stdout=True by default, so all 7 logs are in stdout
        assert self.stdout == schema.list([
            schema.str % '{"level": "trace", "msg": "Trace message"}',
            schema.str % '{"level": "debug", "msg": "Debug message"}',
            schema.str % '{"level": "info", "msg": "Info message"}',
            schema.str % '{"level": "warning", "msg": "Warning message"}',
            schema.str % '{"level": "error", "msg": "Error message"}',
            schema.str % '{"level": "fatal", "msg": "Fatal message"}',
            schema.str % '{"level": "panic", "msg": "Panic message"}'
        ])

    def then_stderr_should_contain_error_levels(self):
        # warning, error, fatal, panic should be in stderr (default stderr_log_levels)
        assert self.stderr == schema.list([
            schema.str % '{"level": "warning", "msg": "Warning message"}',
            schema.str % '{"level": "error", "msg": "Error message"}',
            schema.str % '{"level": "fatal", "msg": "Fatal message"}',
            schema.str % '{"level": "panic", "msg": "Panic message"}'
        ])
