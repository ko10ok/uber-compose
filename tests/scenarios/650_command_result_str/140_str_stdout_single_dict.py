import vedro
from d42 import schema

from uber_compose.vedro_plugin.base_structures.common_json_cli import CommandResult


class Scenario(vedro.Scenario):
    subject = 'CommandResult.__str__ with single dict element in stdout'

    def given_command_result_with_single_dict_stdout(self):
        self.result = CommandResult(
            stdout=[{'level': 'info', 'msg': 'test'}],
            stderr=[],
            cmd='test-command',
            env={'VAR': 'value'}
        )

    def when_user_converts_to_string(self):
        self.result_str = str(self.result)

    def then_it_should_match_expected_format(self):
        expected = """CommandResult(
    stdout = [{'level': 'info', 'msg': 'test'}],
    stderr = [],
    cmd = 'test-command',
    env = {'VAR': 'value'}
)"""
        assert self.result_str == schema.str % expected
