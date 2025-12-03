import vedro
from d42 import schema

from uber_compose.vedro_plugin.base_structures.common_json_cli import CommandResult


class Scenario(vedro.Scenario):
    subject = 'CommandResult.__str__ with multiple dicts (3+ keys each) in stdout'

    def given_command_result_with_multiple_dicts_many_keys(self):
        self.result = CommandResult(
            stdout=[
                {'level': 'info', 'msg': 'first', 'timestamp': '10:00:00'},
                {'level': 'debug', 'msg': 'second', 'timestamp': '10:01:00'},
                {'level': 'error', 'msg': 'third', 'timestamp': '10:02:00'}
            ],
            stderr=[],
            cmd='test-command',
            env={'VAR': 'value'}
        )

    def when_user_converts_to_string(self):
        self.result_str = str(self.result)

    def then_it_should_match_expected_format(self):
        expected = """CommandResult(
    stdout = [
        {
            'level': 'info',
            'msg': 'first',
            'timestamp': '10:00:00'
        },
        {
            'level': 'debug',
            'msg': 'second',
            'timestamp': '10:01:00'
        },
        {
            'level': 'error',
            'msg': 'third',
            'timestamp': '10:02:00'
        }
    ],
    stderr = [],
    cmd = 'test-command',
    env = {'VAR': 'value'}
)"""
        assert self.result_str == schema.str % expected
