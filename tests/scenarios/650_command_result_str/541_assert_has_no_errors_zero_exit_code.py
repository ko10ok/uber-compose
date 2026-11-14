import vedro

from uber_compose.vedro_plugin.base_structures.common_json_cli import CommandResult


class Scenario(vedro.Scenario):
    subject = 'assert CommandResult.has_no_errors() with zero exit code should pass'

    def given_command_result_with_zero_exit_code(self):
        self.result = CommandResult(
            stdout=['log line'],
            stderr=[],
            cmd='test-command',
            env={'VAR': 'value'},
            exit_code=0,
        )

    def when_user_asserts_has_no_errors(self):
        self.returned = self.result.has_no_errors()

    def then_has_no_errors_should_return_self(self):
        assert self.returned is self.result
