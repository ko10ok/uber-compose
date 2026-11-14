from unittest.mock import AsyncMock
from unittest.mock import Mock

from d42 import schema
import vedro

from uber_compose import CommonJsonCli
from uber_compose.helpers.exec_result import ExecResult


class Scenario(vedro.Scenario):
    subject = 'CommandResult rendered through CommonJsonCli contains exit code'

    def given_mocked_client_with_nonzero_exit_code(self):
        self.cli_client_mock = Mock()
        self.result_logs = b'{"level": "stdout", "message": "done"}'
        self.mock_exec_result = ExecResult(
            stdout=self.result_logs,
            cmd='test_command',
            exit_code=7,
        )
        self.cli_client_mock.exec = AsyncMock(return_value=self.mock_exec_result)

    def given_common_json_cli(self):
        self.json_cli = CommonJsonCli(cli_client=self.cli_client_mock)

    async def when_user_executes_command(self):
        self.result = await self.json_cli.exec(
            container='test_container',
            command='test_command',
        )

    def then_result_exit_code_should_be_preserved(self):
        assert self.result.exit_code == 7

    def then_rendered_result_should_contain_exit_code(self):
        assert str(self.result) == schema.str.contains('exit_code = 7')
