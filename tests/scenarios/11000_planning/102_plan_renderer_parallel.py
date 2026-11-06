from textwrap import dedent

import vedro

from uber_compose.parallel_plugin.planner import PlanEnvironment
from uber_compose.parallel_plugin.planner import PlanReplica
from uber_compose.parallel_plugin.planner import PlanService
from uber_compose.parallel_plugin.planner import RunPlan
from uber_compose.parallel_plugin.planner import render_plan


class Scenario(vedro.Scenario):
    subject = 'render parallel uber-compose plan'

    async def given_parallel_plan(self):
        self.plan = RunPlan(
            compose_config='default',
            compose_files='docker-compose.yaml',
            parallel=True,
            uc_mt_enabled=True,
            max_concurrent_envs=1,
            environments=(
                PlanEnvironment(
                    name='env-a',
                    services=(
                        PlanService(name='api', env={'DB_NAME': 'app_[[env_id]]'}),
                        PlanService(name='db', mode='SINGLETON'),
                    ),
                    replicas=(
                        PlanReplica(
                            worker_id=0,
                            replica_index=0,
                            replicas_total=3,
                            namespace='w0-ab12',
                            test_paths=(
                                'scenarios/test_a.py',
                                'scenarios/test_b.py',
                                'scenarios/test_c.py',
                                'scenarios/test_d.py',
                            ),
                        ),
                        PlanReplica(
                            worker_id=1,
                            replica_index=1,
                            replicas_total=3,
                            namespace='w1-ab12',
                            test_paths=(
                                'scenarios/test_e.py',
                                'scenarios/test_f.py',
                            ),
                        ),
                        PlanReplica(
                            worker_id=2,
                            replica_index=2,
                            replicas_total=3,
                            namespace='w2-ab12',
                            test_paths=(
                                'scenarios/test_g.py',
                            ),
                        ),
                    ),
                ),
                PlanEnvironment(
                    name='env-b',
                    services=(PlanService(name='api'),),
                    replicas=(
                        PlanReplica(
                            worker_id=3,
                            replica_index=0,
                            replicas_total=1,
                            namespace='w0-cd34',
                            test_paths=(
                                'scenarios/test_h.py',
                                'scenarios/test_i.py',
                            ),
                        ),
                    ),
                ),
            ),
        )

    async def when_level_zero_is_rendered(self):
        self.rendered = render_plan(self.plan)

    async def then_it_should_show_lifecycle_infra_and_worker_tests(self):
        expected = dedent("""
            uber-compose plan
            dry run: nothing will be started

            compose config: default
            lifecycle: env-a[3] || env-b[1]
            infra: root_orchestrator -> workers[4]

            env-a
              services: api, db [singleton]
              replicas[3]:
                w0-env-a[0]  tests[4]: test_a.py, test_b.py, test_c.py, ...
                w1-env-a[1]  tests[2]: test_e.py, test_f.py
                w2-env-a[2]  tests[1]: test_g.py

            env-b
              services: api
              replicas[1]:
                w3-env-b[0]  tests[2]: test_h.py, test_i.py
        """).strip()
        assert self.rendered == expected

    async def when_level_one_is_rendered(self):
        self.rendered_level_one = render_plan(self.plan, level=1)

    async def then_it_should_show_namespaces_settings_and_all_tests(self):
        expected = dedent("""
            uber-compose plan
            dry run: nothing will be started

            compose config: default
            compose files: docker-compose.yaml
            lifecycle: env-a[3] || env-b[1]
            infra: root_orchestrator -> workers[4]
            settings:
              workers_per_env: env-a[3], env-b[1]
              default_workers_per_env: 1
              max_concurrent_envs: 1
              --uc-mt: on
              ignored: max_concurrent_envs (parallel run)

            env-a
              services:
                api
                  env: DB_NAME=app_[[env_id]]
                db [singleton]
              replicas[3]:
                w0-env-a[0]  namespace: w0-ab12  tests[4]: test_a.py, test_b.py, test_c.py, test_d.py
                w1-env-a[1]  namespace: w1-ab12  tests[2]: test_e.py, test_f.py
                w2-env-a[2]  namespace: w2-ab12  tests[1]: test_g.py

            env-b
              services:
                api
              replicas[1]:
                w3-env-b[0]  namespace: w0-cd34  tests[2]: test_h.py, test_i.py
        """).strip()
        assert self.rendered_level_one == expected
