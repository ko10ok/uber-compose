from textwrap import dedent

import vedro

from uber_compose.parallel_plugin.planner import PlanEnvironment
from uber_compose.parallel_plugin.planner import PlanService
from uber_compose.parallel_plugin.planner import RunPlan
from uber_compose.parallel_plugin.planner import render_plan


class Scenario(vedro.Scenario):
    subject = 'render sequential uber-compose plan'

    async def given_sequential_plan(self):
        self.plan = RunPlan(
            compose_config='default',
            compose_files='docker-compose.yaml',
            parallel=False,
            max_concurrent_envs=1,
            environments=(
                PlanEnvironment(
                    name='env-a',
                    services=(
                        PlanService(name='api'),
                        PlanService(name='db', mode='SINGLETON'),
                    ),
                    test_paths=(
                        'scenarios/test_a.py',
                        'scenarios/test_b.py',
                        'scenarios/test_c.py',
                        'scenarios/test_d.py',
                        'scenarios/test_e.py',
                    ),
                ),
                PlanEnvironment(
                    name='env-b',
                    services=(PlanService(name='api'),),
                    test_paths=(
                        'scenarios/test_f.py',
                        'scenarios/test_g.py',
                    ),
                ),
                PlanEnvironment(
                    name='env-c',
                    services=(PlanService(name='worker'),),
                    test_paths=(
                        'scenarios/test_h.py',
                        'scenarios/test_i.py',
                        'scenarios/test_j.py',
                    ),
                ),
            ),
        )

    async def when_level_zero_is_rendered(self):
        self.rendered = render_plan(self.plan)

    async def then_it_should_show_processes_and_lifecycle(self):
        expected = dedent("""
            uber-compose plan
            dry run: nothing will be started

            compose config: default
            lifecycle: env-a -> env-b -> env-c
            infra: root_worker

            env-a
              services: api, db [singleton]
              tests[5]: test_a.py, test_b.py, test_c.py, ...

            env-b
              services: api
              tests[2]: test_f.py, test_g.py

            env-c
              services: worker
              tests[3]: test_h.py, test_i.py, test_j.py
        """).strip()
        assert self.rendered == expected

    async def when_level_one_is_rendered(self):
        self.rendered_level_one = render_plan(self.plan, level=1)

    async def then_it_should_show_settings_and_full_test_lists(self):
        expected = dedent("""
            uber-compose plan
            dry run: nothing will be started

            compose config: default
            compose files: docker-compose.yaml
            lifecycle: env-a -> env-b -> env-c
            infra: root_worker
            settings:
              max_concurrent_envs: 1
              --uc-mt: off

            env-a
              services:
                api
                db [singleton]
              tests[5]: test_a.py, test_b.py, test_c.py, test_d.py, test_e.py

            env-b
              services:
                api
              tests[2]: test_f.py, test_g.py

            env-c
              services:
                worker
              tests[3]: test_h.py, test_i.py, test_j.py
        """).strip()
        assert self.rendered_level_one == expected
