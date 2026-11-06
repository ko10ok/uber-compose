from contexts.isolated_project import isolated_project
from contexts.no_docker_containers import no_docker_containers
from contexts.no_docker_containers import retrieve_all_docker_containers
from contexts.vedro_subprocess_project import vedro_subprocess_project
from d42 import schema
from interfaces.vedro_cli import CliRunner
import vedro


class Scenario(vedro.Scenario):
    subject = 'run vedro with uc disabled'

    async def given_no_docker_containers(self):
        no_docker_containers()

    async def given_isolated_project(self):
        self.project = isolated_project()

    async def given_vedro_project_with_disabled_plugin(self):
        self.project_dir = vedro_subprocess_project(
            vedro_cfg="""
import vedro

from uber_compose import VedroUberCompose


class Config(vedro.Config):
    class Plugins(vedro.Config.Plugins):
        class UberCompose(VedroUberCompose):
            enabled = False
""",
            scenarios={
                'test_no_env.py': """
import vedro


class Scenario(vedro.Scenario):
    subject = 'scenario runs without any environment'

    def when_nothing_special_happens(self):
        self.result = 'ok'

    def then_it_should_just_pass(self):
        assert self.result == 'ok'
"""
            },
        )

    async def when_vedro_is_run(self):
        self.run_result = await CliRunner().run_vedro(self.project_dir, args=['run', 'scenarios/'])

    async def then_it_should_exit_with_code_zero(self):
        assert self.run_result.returncode == 0, self.run_result.stdout + self.run_result.stderr

    async def and_it_should_not_start_any_container(self):
        assert retrieve_all_docker_containers() == schema.list([])
