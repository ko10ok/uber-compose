import vedro
from d42 import schema

from uber_compose.vedro_plugin.base_structures.common_json_cli import CommandResult


class Scenario(vedro.Scenario):
    subject = 'assert CommandResult.has_no_errors() with errors should raise AssertionError'

    def given_command_result_with_errors(self):
        self.result = CommandResult(
            stdout=['log line'],
            stderr=['error log'],
            cmd='test-command',
            env={'VAR': 'value'}
        )

    def when_user_asserts_has_no_errors(self):
        self.exception = None
        try:
            assert self.result.has_no_errors()
        except AssertionError as e:
            self.exception = e

    def then_assertion_should_raise_error(self):
        assert self.exception is not None
        assert isinstance(self.exception, AssertionError)

    def then_error_message_should_match_expected_format(self):
        expected_error = """Command result contains errors:
 CommandResult(
    stdout = ['log line'],
    ❌ stderr = ['error log'],
    cmd = 'test-command',
    env = {'VAR': 'value'}
)"""
        assert str(self.exception) == schema.str % expected_error
