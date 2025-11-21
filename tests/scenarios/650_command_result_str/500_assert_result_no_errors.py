import vedro

from uber_compose.vedro_plugin.base_structures.common_json_cli import CommandResult


class Scenario(vedro.Scenario):
    subject = 'assert CommandResult with no errors should pass'

    def given_command_result_with_no_errors(self):
        self.result = CommandResult(
            stdout=['log line'],
            stderr=[],
            cmd='test-command',
            env={'VAR': 'value'}
        )

    def when_user_asserts_command_result(self):
        assert self.result
