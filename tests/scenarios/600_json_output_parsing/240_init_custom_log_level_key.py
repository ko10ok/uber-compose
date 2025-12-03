import vedro
from d42 import schema

from uber_compose.vedro_plugin.base_structures.common_json_cli import JsonParser


class Scenario(vedro.Scenario):
    subject = 'JsonParser initialization with custom log_level_key'

    def given_parser_with_custom_log_level_key(self):
        self.parser = JsonParser(log_level_key='severity')

    def given_logs_with_custom_level_key(self):
        self.logs = b'''{"severity": "info", "message": "Info message"}
{"severity": "error", "message": "Error message"}
{"severity": "debug", "message": "Debug message"}'''

    def when_user_parses_logs(self):
        self.stdout, self.stderr = self.parser.parse_output_to_json(self.logs)

    def then_it_should_parse_with_custom_key(self):
        assert self.stdout == schema.list(schema.str).len(3)
        assert self.stderr == schema.list(schema.str).len(1)

    def then_it_should_identify_errors_correctly(self):
        assert self.stderr == schema.list([
            schema.str % '{"severity": "error", "message": "Error message"}'
        ])
