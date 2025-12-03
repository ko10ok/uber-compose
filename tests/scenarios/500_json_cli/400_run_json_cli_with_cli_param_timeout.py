import vedro
from d42 import schema
from unittest.mock import AsyncMock, Mock, ANY
from vedro import catched
from uber_compose import CommonJsonCli
from uber_compose.vedro_plugin.base_structures.common_json_cli import CommandResult
from uber_compose.core.docker_compose_shell.interface import TimeOutCheck
from uber_compose.helpers.exec_result import ExecTimeout


class Scenario(vedro.Scenario):
    subject = 'run command through CommonJsonCli with timeout should raise AssertionError'

    def given_mocked_client(self):
        self.cli_client_mock = Mock()

        # Mock a timeout result - ExecTimeout instead of ExecResult
        self.mock_exec_result = ExecTimeout(stdout=b'partial output', cmd='test_command')
        self.cli_client_mock.exec = AsyncMock(return_value=self.mock_exec_result)

    def given_common_json_cli(self):
        self.timeout = TimeOutCheck(attempts=5, delay_s=2.0)
        self.json_cli = CommonJsonCli(
            cli_client=self.cli_client_mock,
            timeout=self.timeout
        )

    def given_command_parameters(self):
        self.container = 'test_container'
        self.command = 'long-running-command --timeout 60'
        self.extra_env = {'TIMEOUT_VAR': '60'}
        # Configure custom timeout with more attempts and longer delay


    async def when_user_executes_command_with_timeout(self):
        with catched(AssertionError) as self.exc_info:
            await self.json_cli.exec(
                container=self.container,
                command=self.command,
                extra_env=self.extra_env,
                timeout=self.timeout
            )

    def then_cli_client_exec_should_be_called(self):
        self.cli_client_mock.exec.assert_called_once()

    def then_cli_client_exec_should_be_called_with_custom_timeout(self):
        self.cli_client_mock.exec.assert_called_with(
            container=self.container,
            command=self.command,
            extra_env=self.extra_env,
            wait=ANY,
            timeout=self.timeout,
        )


    def then_timeout_should_be_passed_correctly(self):
        call_args = self.cli_client_mock.exec.call_args
        timeout_arg = call_args.kwargs.get('timeout')
        assert timeout_arg == self.timeout
        assert timeout_arg.attempts == 5
        assert timeout_arg.delay_s == 2.0

    def then_should_raise_assertion_error_for_timeout(self):
        error_message = str(self.exc_info.value)
        assert 'Expected successful command completion' in error_message
        assert 'ExecTimeout' in error_message

    def then_assertion_error_should_contain_timeout_details(self):
        error_message = str(self.exc_info.value)
        assert 'cmd=test_command' in error_message
        assert 'stdout=b\'partial output\'' in error_message

    def then_assertion_error_should_contain_timeout_parameters(self):
        error_message = str(self.exc_info.value)
        assert 'attempts=5' in error_message
        assert 'delay_s=2.0' in error_message
