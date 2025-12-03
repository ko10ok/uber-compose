import vedro
from d42 import schema

from uber_compose.vedro_plugin.base_structures.common_json_cli import JsonParser


class Scenario(vedro.Scenario):
    subject = 'JsonParser initialization with full_stdout=False'

    def given_parser_with_full_stdout_disabled(self):
        self.parser = JsonParser(full_stdout=False)

    def given_logs_with_errors(self):
        self.logs = b'''{"level": "info", "msg": "Info message"}
{"level": "error", "msg": "Error message"}
{"level": "debug", "msg": "Debug message"}'''

    def when_user_parses_logs(self):
        self.stdout, self.stderr = self.parser.parse_output_to_json(self.logs)

    def then_it_should_not_duplicate_errors_in_stdout(self):
        # With full_stdout=False, errors are only in stderr
        assert self.stdout == schema.list([
            schema.str % '{"level": "info", "msg": "Info message"}',
            schema.str % '{"level": "debug", "msg": "Debug message"}'
        ])

    def then_it_should_have_error_only_in_stderr(self):
        assert self.stderr == schema.list([
            schema.str % '{"level": "error", "msg": "Error message"}'
        ])
