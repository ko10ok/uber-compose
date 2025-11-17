import vedro
from d42 import schema

from uber_compose.vedro_plugin.base_structures.common_json_cli import JsonParser


class Scenario(vedro.Scenario):
    subject = 'parse_output_to_json with multiline JSON'

    def given_json_parser(self):
        self.parser = JsonParser()

    def given_logs_with_newlines_in_content(self):
        # Each log line is still on one line, but contains escaped newlines
        self.logs = b'''{"level": "info", "msg": "Line 1"}
{"level": "error", "msg": "Error\\nwith newline"}
{"level": "info", "msg": "Line 2"}'''

    def when_user_parses_logs(self):
        self.stdout, self.stderr = self.parser.parse_output_to_json(self.logs)

    def then_it_should_parse_correctly(self):
        assert self.stdout == schema.list(schema.str).len(3)
        assert self.stderr == schema.list(schema.str).len(1)

    def then_it_should_preserve_escaped_newlines(self):
        assert self.stderr == schema.list([
            schema.str.contains('newline')
        ])
