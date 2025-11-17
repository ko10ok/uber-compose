import vedro
from d42 import schema

from uber_compose.vedro_plugin.base_structures.common_json_cli import JsonParser


class Scenario(vedro.Scenario):
    subject = 'parse_output_to_json with mixed JSON and non-JSON logs'

    def given_json_parser(self):
        self.parser = JsonParser()

    def given_mixed_logs(self):
        self.logs = b'''{"level": "info", "msg": "JSON line"}
Plain text line without JSON
{"level": "error", "msg": "Error occurred"}
Another plain text line'''

    def when_user_parses_logs(self):
        self.stdout, self.stderr = self.parser.parse_output_to_json(self.logs)

    def then_it_should_parse_json_and_plain_text(self):
        assert self.stdout == schema.list(schema.str).len(4)
        assert self.stderr == schema.list(schema.str).len(3)  # error + 2 plain text lines

    def then_it_should_treat_non_json_as_errors(self):
        # Non-JSON lines are treated as errors
        assert self.stderr == schema.list([
            schema.str.contains('Plain text line without JSON'),
            schema.str % '{"level": "error", "msg": "Error occurred"}',
            schema.str.contains('Another plain text line')
        ])
