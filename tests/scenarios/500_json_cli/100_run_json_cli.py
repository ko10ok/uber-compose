import vedro
from d42 import schema
from unittest.mock import AsyncMock, Mock
from unittest.mock import ANY
from uber_compose import CommonJsonCli
from uber_compose.vedro_plugin.base_structures.common_json_cli import CommandResult


class Scenario(vedro.Scenario):
    subject = 'run command through CommonJsonCli'

    def given_mocked_client(self):
        self.cli_client_mock = Mock()

        self.result_logs = b'''{"level": "info", "message": "Starting process"}
{"level": "debug", "message": "Processing data"}
{"level": "info", "message": "Completed successfully"}'''

        self.mock_exec_result = Mock(stdout=self.result_logs)
        self.cli_client_mock.exec = AsyncMock(return_value=self.mock_exec_result)

    def given_common_json_cli(self):
        self.json_cli = CommonJsonCli(cli_client=self.cli_client_mock)

    def given_command_parameters(self):
        self.container = 'test_container'
        self.command = 'echo "test"'
        self.extra_env = {'TEST_VAR': 'test_value'}

    async def when_user_executes_command(self):
        self.result = await self.json_cli.exec(
            container=self.container,
            command=self.command,
            extra_env=self.extra_env
        )

    def then_cli_client_exec_should_be_called(self):
        self.cli_client_mock.exec.assert_called_once()

    def then_cli_client_exec_should_be_called_with_correct_params(self):
        self.cli_client_mock.exec.assert_called_with(
            container=self.container,
            command=self.command,
            extra_env=self.extra_env,
            wait=ANY
        )

    def then_result_should_be_command_result(self):
        assert isinstance(self.result, CommandResult)

    def then_result_should_contain_parsed_stdout(self):
        assert self.result.stdout == schema.list([
            schema.str.contains('Starting process'),
            schema.str.contains('Processing data'),
            schema.str.contains('Completed successfully'),
        ]).len(3)

    def then_result_should_have_no_errors(self):
        assert self.result.stderr == []
        assert self.result.has_no_errors()

    def then_result_should_contain_command_info(self):
        assert self.result.cmd == self.command
        assert self.result.env == self.extra_env
