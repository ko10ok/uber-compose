from unittest.mock import AsyncMock
from unittest.mock import Mock

import vedro
from vedro import catched

from uber_compose import CommonJsonCli


class Scenario(vedro.Scenario):
    subject = 'run command through CommonJsonCli with no container defined should raise AssertionError'

    def given_mocked_client(self):
        self.cli_client_mock = Mock()
        self.cli_client_mock.exec = AsyncMock()

    def given_common_json_cli_without_container(self):
        # Create CommonJsonCli without specifying container
        self.json_cli = CommonJsonCli(
            cli_client=self.cli_client_mock
        )

    def given_command_parameters(self):
        self.command = 'echo "test"'
        self.extra_env = {'TEST_VAR': 'test_value'}

    async def when_user_executes_command_without_container(self):
        with catched(AssertionError) as self.exc_info:
            await self.json_cli.exec(
                command=self.command,
                extra_env=self.extra_env
                # Note: not passing container parameter
            )

    def then_should_raise_assertion_error_for_missing_container(self):
        error_message = str(self.exc_info.value)
        assert 'No container specified' in error_message
        assert 'Container must be specified either in method call or in CommonJsonCli initialization' in error_message

    def then_cli_client_exec_should_not_be_called(self):
        # exec should not be called because error occurs before exec is invoked
        self.cli_client_mock.exec.assert_not_called()
