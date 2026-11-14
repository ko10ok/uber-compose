from unittest.mock import ANY
from unittest.mock import AsyncMock
from unittest.mock import Mock

import vedro

from uber_compose import CommonJsonCli
from uber_compose import PidofExecStrategy
from uber_compose import StatusFileExecStrategy
from uber_compose.helpers.exec_result import ExecResult


class Scenario(vedro.Scenario):
    subject = 'CommonJsonCli passes configured exec strategy to client and returns exit code'

    def given_mocked_client(self):
        self.cli_client_mock = Mock()
        self.mock_result = ExecResult(
            stdout=b'{"level": "info", "message": "done"}',
            cmd='test_command',
            exit_code=9,
        )
        self.cli_client_mock.exec = AsyncMock(return_value=self.mock_result)

    def given_json_cli_with_exec_strategy(self):
        self.json_cli = CommonJsonCli(
            cli_client=self.cli_client_mock,
            exec=PidofExecStrategy,
        )

    async def when_user_executes_command(self):
        self.result = await self.json_cli.exec(
            container='test_container',
            command='test_command',
        )

    def then_client_should_receive_configured_strategy(self):
        self.cli_client_mock.exec.assert_awaited_once_with(
            container='test_container',
            command='test_command',
            extra_env=None,
            wait=ANY,
            timeout=ANY,
            life_cycle_policy=ANY,
            exec=PidofExecStrategy,
        )

    def then_result_should_contain_exit_code(self):
        assert self.result.exit_code == 9


class PerCallScenario(vedro.Scenario):
    subject = 'CommonJsonCli per-call exec strategy overrides configured strategy'

    def given_mocked_client(self):
        self.cli_client_mock = Mock()
        self.cli_client_mock.exec = AsyncMock(
            return_value=ExecResult(stdout=b'{"level": "info"}', cmd='test_command', exit_code=0)
        )

    def given_json_cli_with_exec_strategy(self):
        self.json_cli = CommonJsonCli(
            cli_client=self.cli_client_mock,
            exec=PidofExecStrategy,
        )

    async def when_user_executes_command_with_override(self):
        self.result = await self.json_cli.exec(
            container='test_container',
            command='test_command',
            exec=StatusFileExecStrategy,
        )

    def then_client_should_receive_overridden_strategy(self):
        self.cli_client_mock.exec.assert_awaited_once_with(
            container='test_container',
            command='test_command',
            extra_env=None,
            wait=ANY,
            timeout=ANY,
            life_cycle_policy=ANY,
            exec=StatusFileExecStrategy,
        )

    def then_result_should_contain_exit_code(self):
        assert self.result.exit_code == 0
