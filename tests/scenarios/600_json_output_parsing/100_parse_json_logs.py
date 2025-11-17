import vedro
from d42 import schema

from uber_compose.vedro_plugin.base_structures.common_json_cli import JsonParser


class Scenario(vedro.Scenario):
    subject = 'parse_output_to_json with valid JSON logs'

    def given_json_parser(self):
        self.parser = JsonParser()

    def given_valid_json_logs(self):
        self.logs = b'''{"level": "info", "msg": "Starting service"}
{"level": "debug", "msg": "Debug message"}
{"level": "error", "msg": "Something went wrong"}
{"level": "info", "msg": "Service started"}'''

    def when_user_parses_logs(self):
        self.stdout, self.stderr = self.parser.parse_output_to_json(self.logs)

    def then_it_should_have_all_in_stdout(self):
        # full_stdout=True by default, so all logs are in stdout
        assert self.stdout == schema.list([
            schema.str % '{"level": "info", "msg": "Starting service"}',
            schema.str % '{"level": "debug", "msg": "Debug message"}',
            schema.str % '{"level": "error", "msg": "Something went wrong"}',
            schema.str % '{"level": "info", "msg": "Service started"}'
        ])

    def then_it_should_return_parsed_errors(self):
        assert self.stderr == schema.list([
            schema.str % '{"level": "error", "msg": "Something went wrong"}'
        ])
