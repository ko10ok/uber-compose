import vedro
from d42 import schema

from uber_compose.vedro_plugin.base_structures.common_json_cli import JsonParser


class Scenario(vedro.Scenario):
    subject = 'JsonParser initialization with dict_output=True'

    def given_parser_with_dict_output(self):
        self.parser = JsonParser(dict_output=True)

    def given_json_logs(self):
        self.logs = b'''{"level": "info", "msg": "Info message"}
{"level": "error", "msg": "Error message"}'''

    def when_user_parses_logs(self):
        self.stdout, self.stderr = self.parser.parse_output_to_json(self.logs)

    def then_it_should_return_dicts(self):
        assert self.stdout == schema.list([
            schema.dict({
                'level': schema.str('info'),
                'msg': schema.str('Info message')
            }),
            schema.dict({
                'level': schema.str('error'),
                'msg': schema.str('Error message')
            })
        ])

    def then_it_should_have_error_dict_in_stderr(self):
        assert self.stderr == schema.list([
            schema.dict({
                'level': schema.str('error'),
                'msg': schema.str('Error message')
            })
        ])
