import vedro
from d42 import schema
from unittest.mock import AsyncMock, Mock, ANY

from uber_compose import CommonJsonCli
from uber_compose.vedro_plugin.base_structures.common_json_cli import CommandResult


class Scenario(vedro.Scenario):
    subject = 'run command through CommonJsonCli with errors in result'

    def given_mocked_client(self):
        self.cli_client_mock = Mock()

        # Логи содержат ошибки (error, warning) и обычные сообщения
        self.result_logs = b'''{"level": "info", "message": "Starting process"}
{"level": "warning", "message": "Low memory detected"}
{"level": "error", "message": "Database connection failed"}
{"level": "info", "message": "Retrying connection"}
{"level": "fatal", "message": "Critical system error"}'''

        self.mock_exec_result = Mock(stdout=self.result_logs)
        self.cli_client_mock.exec = AsyncMock(return_value=self.mock_exec_result)

    def given_common_json_cli(self):
        self.json_cli = CommonJsonCli(cli_client=self.cli_client_mock)

    def given_command_parameters(self):
        self.container = 'test_container'
        self.command = 'run-app --config prod'
        self.extra_env = {'ENV': 'production'}

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

    def then_result_should_contain_all_logs_in_stdout(self):
        # В stdout должны быть все логи (full_stdout=True по умолчанию)
        assert self.result.stdout == schema.list([
            schema.str.contains('Starting process'),
            schema.str.contains('Low memory detected'),
            schema.str.contains('Database connection failed'),
            schema.str.contains('Retrying connection'),
            schema.str.contains('Critical system error'),
        ]).len(5)

    def then_result_should_contain_errors_in_stderr(self):
        # В stderr должны быть только ошибки (warning, error, fatal)
        assert self.result.stderr == schema.list([
            schema.str.contains('Low memory detected'),
            schema.str.contains('Database connection failed'),
            schema.str.contains('Critical system error'),
        ]).len(3)

    def then_result_should_have_errors(self):
        assert not self.result.has_no_errors()
        assert len(self.result.stderr) > 0

    def then_result_should_contain_command_info(self):
        assert self.result.cmd == self.command
        assert self.result.env == self.extra_env
