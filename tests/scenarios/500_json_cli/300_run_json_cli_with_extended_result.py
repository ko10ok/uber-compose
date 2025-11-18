import vedro
from d42 import schema
from dataclasses import dataclass
from unittest.mock import AsyncMock, Mock, ANY

from uber_compose.vedro_plugin.base_structures.common_json_cli import (
    CommonJsonCli,
    CommandResult,
)


@dataclass
class ExtendedCommandResult(CommandResult):
    extra_param: str = ""
    complex_extra_param: dict = None


class Scenario(vedro.Scenario):
    subject = 'run command through CommonJsonCli with extended CommandResult type'

    def given_mocked_client(self):
        self.cli_client_mock = Mock()

        self.result_logs = b'''{"level": "info", "message": "Starting process"}
{"level": "debug", "message": "Processing data"}
{"level": "info", "message": "Completed successfully"}'''

        self.mock_exec_result = Mock(stdout=self.result_logs)
        self.cli_client_mock.exec = AsyncMock(return_value=self.mock_exec_result)

    def given_common_json_cli_with_extended_result(self):
        # Create CommonJsonCli with parametric type ExtendedCommandResult
        self.json_cli: CommonJsonCli[ExtendedCommandResult] = CommonJsonCli(
            cli_client=self.cli_client_mock,
            result_factory=ExtendedCommandResult,
        )

    def given_command_parameters(self):
        self.container = 'test_container'
        self.command = 'test-command'
        self.extra_env = {'VAR': 'value'}
        self.extra_param_value = 'custom_extra_value'

    async def when_user_executes_command_with_extra_params(self):
        self.result = await self.json_cli.exec(
            container=self.container,
            command=self.command,
            extra_env=self.extra_env,
            command_result_extra={
                'extra_param': self.extra_param_value,
                'complex_extra_param': {'key': 'value'}
            }
        )

    def then_result_should_be_extended_command_result(self):
        # Check that result is ExtendedCommandResult instance
        assert isinstance(self.result, ExtendedCommandResult)
        assert isinstance(self.result, CommandResult)

    def then_result_should_contain_standard_fields(self):
        assert self.result.cmd == self.command
        assert self.result.env == self.extra_env
        assert self.result.stderr == []
        assert self.result.has_no_errors()
        assert self.result.stdout == schema.list([
            schema.str.contains('Starting process'),
            schema.str.contains('Processing data'),
            schema.str.contains('Completed successfully'),
        ]).len(3)

    def then_result_should_contain_extra_param(self):
        # Check that extra_param is present
        assert hasattr(self.result, 'extra_param')
        assert self.result.extra_param == self.extra_param_value

    def then_result_should_contain_complex_extra_param(self):
        # Check that complex_extra_param is present
        assert hasattr(self.result, 'complex_extra_param')
        assert self.result.complex_extra_param == {'key': 'value'}

    def then_cli_client_should_be_called_correctly(self):
        self.cli_client_mock.exec.assert_called_once_with(
            container=self.container,
            command=self.command,
            extra_env=self.extra_env,
            wait=ANY
        )
