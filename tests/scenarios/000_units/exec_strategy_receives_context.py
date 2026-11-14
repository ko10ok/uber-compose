from unittest.mock import AsyncMock
from unittest.mock import Mock

import vedro

from uber_compose import ExecContext
from uber_compose import ExecLifeCyclePolicy
from uber_compose import ExecStrategy
from uber_compose import ProcessExit
from uber_compose import SystemUberCompose
from uber_compose import TimeOutCheck
from uber_compose.core.docker_compose_shell.types import ServicesComposeState
from uber_compose.helpers.exec_result import ExecResult
from uber_compose.helpers.labels import Label


class CapturingStrategy(ExecStrategy):
    context: ExecContext | None = None

    async def execute(self, context: ExecContext):
        type(self).context = context
        return ExecResult(
            stdout=b'captured\n',
            cmd=context.command,
            exit_code=42,
        )


class Scenario(vedro.Scenario):
    subject = 'custom exec strategy receives full exec context'

    def given_mocked_client(self):
        self.client = SystemUberCompose.__new__(SystemUberCompose)
        self.shell = Mock()
        self.shell.dc_state = AsyncMock(return_value=ServicesComposeState(''))
        self.client.system_docker_compose = Mock()
        self.client.system_docker_compose.get_dc_shell = Mock(return_value=self.shell)
        self.client._resolve_exec_service_state = Mock(
            return_value=Mock(labels={Label.SERVICE_NAME: 'resolved-s1'})
        )

    def given_exec_parameters(self):
        self.extra_env = {'AAA': '1'}
        self.timeout = TimeOutCheck(attempts=3, delay_s=0.1)
        self.life_cycle_policy = ExecLifeCyclePolicy(
            kill_before_same_old_command_running=False,
            kill_after_command_still_running=False,
            break_on_timeout=False,
        )

    async def when_user_exec_with_custom_strategy(self):
        self.result = await self.client.exec(
            container='s1',
            command='echo hi',
            extra_env=self.extra_env,
            wait=ProcessExit(),
            timeout=self.timeout,
            life_cycle_policy=self.life_cycle_policy,
            exec=CapturingStrategy,
        )

    def then_result_should_come_from_strategy(self):
        assert self.result.stdout == b'captured\n'
        assert self.result.exit_code == 42

    def then_strategy_should_receive_all_exec_context(self):
        context = CapturingStrategy.context
        assert isinstance(context, ExecContext)
        assert context.shell is self.shell
        assert context.container == 'resolved-s1'
        assert context.command == 'echo hi'
        assert context.extra_env == self.extra_env
        assert context.wait == ProcessExit()
        assert context.timeout == self.timeout
        assert context.life_cycle_policy == self.life_cycle_policy
