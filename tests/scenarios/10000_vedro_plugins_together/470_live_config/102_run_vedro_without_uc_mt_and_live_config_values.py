import json

from contexts.compose_file import compose_file
from contexts.isolated_project import isolated_project
from contexts.no_docker_containers import no_docker_containers
from contexts.vedro_subprocess_project import vedro_subprocess_project
from d42 import schema
from helpers.env_vars import patch_env
from interfaces.vedro_cli import CliRunner
import vedro
import vedro.plugins.temp_keeper as temp_keeper


class Scenario(vedro.Scenario):
    subject = 'run vedro without --uc-mt and live config values in a single process'

    async def given_no_docker_containers(self):
        no_docker_containers()

    async def given_isolated_project(self):
        self.project = isolated_project()
        self.compose_filename = 'docker-compose.yaml'
        compose_file(
            self.compose_filename,
            content="""
version: "3"

services:
  s1:
    image: busybox:stable
    command: 'sh -c "trap : TERM INT; sleep 604800; wait"'
"""
        )

    async def given_observations_directory_and_live_env_vars(self):
        worker_env = (
            'UC_WORKER_ID',
            'UC_WORKERS_TOTAL',
            'UC_WORKER_GROUPS',
            'UC_NAMESPACE_MAP',
            'UC_WORKER_REPLICA_INDEX',
            'UC_ENV_REPLICAS_TOTAL',
        )
        self.observations_dir = temp_keeper.create_tmp_dir(prefix='uc-sequential-')
        patch_env({
            'UC_TEST_OBSERVATIONS_DIR': str(self.observations_dir),
            'UC_LIVE_RAW': 'raw-[[namespace]]-[[worker_id]]',
            'UC_LIVE_STR': 'str-[[namespace]]',
            'UC_LIVE_INT': '[[worker_id]]42',
            'UC_LIVE_MISSING': None,
            **{name: None for name in worker_env},
        })

    async def given_vedro_project(self):
        live_config = """
import cabina

from uber_compose import live_env


class Config(cabina.Config, cabina.Section):
    class Backend(cabina.Section):
        literal: str = live_env.literal('literal-[[namespace]]-w[[worker_id]]')
        raw: str = live_env.raw('UC_LIVE_RAW')
        prefixed: str = live_env.str('UC_LIVE_STR')
        port: int = live_env.int('UC_LIVE_INT')
        default: str = live_env.raw('UC_LIVE_MISSING', default='default-[[namespace]]')
"""
        scenario_template = """
import json
import os

import vedro

from live_config import Config

from uber_compose import Environment
from uber_compose import Service
from uber_compose import TheUberCompose


class Scenario(vedro.Scenario):
    subject = 'scenario __NAME__ records live config and process identity'
    env = Environment(Service('s1'), description='env-a')

    def when_live_config_values_are_recorded(self):
        observations_dir = os.environ['UC_TEST_OBSERVATIONS_DIR']
        with open(os.path.join(observations_dir, '__NAME__.json'), 'w') as file:
            json.dump({
                'pid': os.getpid(),
                'worker_id': os.environ.get('UC_WORKER_ID'),
                'workers_total': os.environ.get('UC_WORKERS_TOTAL'),
                'env_id': TheUberCompose.current_env_id(),
                'namespace': TheUberCompose.current_namespace(),
                'literal': Config.Backend.literal,
                'raw': Config.Backend.raw,
                'prefixed': Config.Backend.prefixed,
                'port': Config.Backend.port,
                'default': Config.Backend.default,
            }, file)
"""
        vedro_cfg = """
import vedro

from uber_compose import ComposeConfig
from uber_compose import DEFAULT_COMPOSE
from uber_compose import VedroUberCompose
from uber_compose import VedroUberComposeParallel


class Config(vedro.Config):
    class Plugins(vedro.Config.Plugins):
        class UberCompose(VedroUberCompose):
            enabled = True
            compose_cfgs = {
                DEFAULT_COMPOSE: ComposeConfig(
                    compose_files="__COMPOSE_FILE__",
                    default_workers_per_env=2,
                ),
            }

        class UberComposeParallel(VedroUberComposeParallel):
            enabled = True
"""
        self.project_dir = vedro_subprocess_project(
            vedro_cfg=vedro_cfg.replace('__COMPOSE_FILE__', self.compose_filename),
            scenarios={
                f'test_{name}.py': scenario_template.replace('__NAME__', name)
                for name in ('env_a_0', 'env_a_1')
            },
        )
        (self.project_dir / 'live_config.py').write_text(live_config)

    async def when_vedro_is_run_without_uc_mt(self):
        self.run_result = await CliRunner().run_vedro(
            self.project_dir,
            args=['run', 'scenarios/'],
        )

    async def then_observations_should_match_single_process_schema(self):
        assert self.run_result.returncode == 0, self.run_result.stdout + self.run_result.stderr
        observations = {
            file.stem: json.loads(file.read_text())
            for file in self.observations_dir.glob('*.json')
        }

        assert observations == schema.dict({
            'env_a_0': schema.dict({
                'pid': schema.int,
                'worker_id': schema.none,
                'workers_total': schema.none,
                'env_id': schema.str('default_env_id'),
                'namespace': schema.str('default_env_id'),
                'literal': schema.str('literal-default_env_id-w0'),
                'raw': schema.str('raw-default_env_id-0'),
                'prefixed': schema.str('str-default_env_id'),
                'port': schema.int(42),
                'default': schema.str('default-default_env_id'),
            }),
            'env_a_1': schema.dict({
                'pid': schema.int,
                'worker_id': schema.none,
                'workers_total': schema.none,
                'env_id': schema.str('default_env_id'),
                'namespace': schema.str('default_env_id'),
                'literal': schema.str('literal-default_env_id-w0'),
                'raw': schema.str('raw-default_env_id-0'),
                'prefixed': schema.str('str-default_env_id'),
                'port': schema.int(42),
                'default': schema.str('default-default_env_id'),
            }),
        })
        assert observations['env_a_0']['pid'] == observations['env_a_1']['pid']
