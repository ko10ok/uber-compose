import vedro

from uber_compose.vedro_plugin.base_structures.common_json_cli import CommandResult


class Scenario(vedro.Scenario):
    subject = 'assert CommandResult.has_no_errors() with nonzero exit code should raise AssertionError'

    def given_command_result_with_nonzero_exit_code(self):
        self.result = CommandResult(
            stdout=['log line'],
            stderr=[],
            cmd='test-command',
            env={'VAR': 'value'},
            exit_code=7,
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
