import vedro
from d42 import schema

from uber_compose.vedro_plugin.base_structures.common_json_cli import JsonParser


class Scenario(vedro.Scenario):
    subject = 'JsonParser with dict_output=True and mixed JSON and non-JSON logs'

    def given_parser_with_dict_output(self):
        self.parser = JsonParser(dict_output=True)

    def given_mixed_logs(self):
        self.logs = b'''{"level": "info", "msg": "Valid JSON line"}
Plain text line without JSON
{"level": "error", "msg": "Error occurred"}
Another plain text line
{"level": "debug", "msg": "Debug info"}'''

    def when_user_parses_logs(self):
        self.stdout, self.stderr = self.parser.parse_output_to_json(self.logs)

    def then_it_should_parse_valid_json_as_dicts(self):
        # Valid JSON lines should be parsed as dicts
        assert self.stdout == schema.list([
            schema.dict({
                'level': schema.str('info'),
                'msg': schema.str('Valid JSON line')
            }),
            schema.dict({'raw': schema.str.contains('Plain text line without JSON')}),
            schema.dict({
                'level': schema.str('error'),
                'msg': schema.str('Error occurred')
            }),
            schema.dict({'raw': schema.str.contains('Another plain text line')}),
            schema.dict({
                'level': schema.str('debug'),
                'msg': schema.str('Debug info')
            })
        ])

    def then_it_should_wrap_non_json_in_raw_dict(self):
        # Non-JSON lines should be wrapped in {'raw': ...} when dict_output=True
        assert self.stdout[1] == schema.dict({
            'raw': schema.str('Plain text line without JSON')
        })
        assert self.stdout[3] == schema.dict({
            'raw': schema.str('Another plain text line')
        })

    def then_it_should_have_errors_in_stderr(self):
        # Non-JSON lines and error level lines should be in stderr
        assert self.stderr == schema.list([
            schema.dict({'raw': schema.str('Plain text line without JSON')}),
            schema.dict({
                'level': schema.str('error'),
                'msg': schema.str('Error occurred')
            }),
            schema.dict({'raw': schema.str('Another plain text line')})
        ])
