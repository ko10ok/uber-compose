import vedro
from d42 import schema

from uber_compose.vedro_plugin.base_structures.common_json_cli import JsonParser


class Scenario(vedro.Scenario):
    subject = 'parse_output_to_json with empty logs'

    def given_json_parser(self):
        self.parser = JsonParser()

    def given_empty_logs(self):
        self.logs = b''

    def when_user_parses_empty_logs(self):
        self.stdout, self.stderr = self.parser.parse_output_to_json(self.logs)

    def then_it_should_return_empty_lists(self):
        assert self.stdout == schema.list.len(0)
        assert self.stderr == schema.list.len(0)
