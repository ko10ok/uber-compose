import os

from helpers.env_vars import patch_env
import vedro

from uber_compose import Environment
from uber_compose import Service
from uber_compose import live_env
from uber_compose.helpers.current_env import CurrentEnvContext
from uber_compose.helpers.current_env import reset_current_env_id
from uber_compose.helpers.current_env import set_current_env_context


def _set_context(env_id: str, worker_id: int = 1) -> None:
    set_current_env_context(CurrentEnvContext(
        env_id=env_id,
        env=Environment(Service('db'), description='env-a'),
        worker_id=worker_id,
        workers_total=4,
        namespace=env_id,
        run_id='run-123',
    ))


class LiveConfig(vedro.Config):
    VALUE = live_env.raw('UC_LIVE_CONFIG')
    LITERAL = live_env.literal('db-[[namespace]]')


class StaticLiveConfig(vedro.Config):
    STATIC_LITERAL = live_env.literal('static-[[namespace]]-[[worker_id]]')
    STATIC_ENV = live_env.raw('UC_STATIC_CONFIG')
    STATIC_STR = live_env.str('UC_STATIC_STR')
    STATIC_DEFAULT = live_env.raw('UC_STATIC_MISSING', default='static-[[namespace]]')
    STATIC_INT = live_env.int('UC_STATIC_PORT')


class LiveEnvStaticDeclarationScenario(vedro.Scenario):
    subject = 'live env substitutes placeholders in statically declared config values'

    async def given_active_worker_context(self):
        reset_current_env_id()
        vedro.defer(reset_current_env_id)
        _set_context('w1-a1b2', worker_id=1)
        patch_env({
            'UC_STATIC_CONFIG': 'static-env-[[namespace]]-[[worker_id]]',
            'UC_STATIC_STR': 'static-str-[[namespace]]-[[worker_id]]',
            'UC_STATIC_MISSING': None,
            'UC_STATIC_PORT': '[[worker_id]]42',
        })

    async def when_static_config_values_are_read(self):
        self.first_literal = StaticLiveConfig.STATIC_LITERAL
        self.first_env = StaticLiveConfig.STATIC_ENV
        self.first_str = StaticLiveConfig.STATIC_STR
        self.first_default = StaticLiveConfig.STATIC_DEFAULT
        self.first_int = StaticLiveConfig.STATIC_INT

        _set_context('w2-c3d4', worker_id=2)
        self.second_literal = StaticLiveConfig.STATIC_LITERAL
        self.second_env = StaticLiveConfig.STATIC_ENV
        self.second_str = StaticLiveConfig.STATIC_STR
        self.second_default = StaticLiveConfig.STATIC_DEFAULT
        self.second_int = StaticLiveConfig.STATIC_INT

    async def then_literal_should_be_substituted_per_context(self):
        assert self.first_literal == 'static-w1-a1b2-1'
        assert self.second_literal == 'static-w2-c3d4-2'

    async def and_static_env_value_should_be_substituted_per_context(self):
        assert self.first_env == 'static-env-w1-a1b2-1'
        assert self.second_env == 'static-env-w2-c3d4-2'

    async def and_static_str_value_should_be_substituted_per_context(self):
        assert self.first_str == 'static-str-w1-a1b2-1'
        assert self.second_str == 'static-str-w2-c3d4-2'

    async def and_static_default_should_be_substituted_per_context(self):
        assert self.first_default == 'static-w1-a1b2'
        assert self.second_default == 'static-w2-c3d4'

    async def and_static_int_should_be_parsed_after_substitution(self):
        assert self.first_int == 142
        assert self.second_int == 242


class LiveEnvConfigAttributeScenario(vedro.Scenario):
    subject = 'live env keeps config attributes bound to the current environment'

    async def given_active_worker_context(self):
        reset_current_env_id()
        vedro.defer(reset_current_env_id)
        _set_context('w1-a1b2')
        patch_env({'UC_LIVE_CONFIG': 'http://db-[[namespace]]'})

    async def when_config_attribute_is_read(self):
        self.first_value = LiveConfig.VALUE
        self.first_literal = LiveConfig.LITERAL
        _set_context('w2-c3d4', worker_id=2)
        self.second_value = LiveConfig.VALUE
        self.second_literal = LiveConfig.LITERAL

    async def then_each_read_should_use_the_current_context(self):
        assert self.first_value == 'http://db-w1-a1b2'
        assert self.second_value == 'http://db-w2-c3d4'
        assert self.first_literal == 'db-w1-a1b2'
        assert self.second_literal == 'db-w2-c3d4'


class LiveEnvPlaceholderScenario(vedro.Scenario):
    subject = 'live env substitutes current environment placeholders on every access'

    async def given_active_worker_context(self):
        reset_current_env_id()
        vedro.defer(reset_current_env_id)
        _set_context('w1-a1b2')

    async def given_env_value_with_placeholders(self):
        patch_env({
            'UC_LIVE_URL': 'http://db-[[namespace]]/[[worker_id]]/[[env_id]]/[[test_run_id]]',
        })

    async def when_live_value_is_created_and_read(self):
        self.live_url = live_env.raw('UC_LIVE_URL')
        self.first_url = self.live_url.get()

    async def and_context_is_switched_to_another_worker(self):
        _set_context('w2-c3d4', worker_id=2)
        self.second_url = self.live_url.get()

    async def then_each_read_should_use_the_placeholders_of_the_current_context(self):
        assert self.first_url == 'http://db-w1-a1b2/1/w1-a1b2/run-123'
        assert self.second_url == 'http://db-w2-c3d4/2/w2-c3d4/run-123'


class LiveEnvNoCacheScenario(vedro.Scenario):
    subject = 'live env re-reads environment variables instead of caching the first value'

    async def given_active_worker_context(self):
        reset_current_env_id()
        vedro.defer(reset_current_env_id)
        _set_context('w1-a1b2')
        patch_env({'UC_LIVE_VALUE': 'first'})

    async def when_env_changes_between_reads(self):
        self.live_value = live_env.raw('UC_LIVE_VALUE')
        self.first_value = self.live_value.get()
        os.environ['UC_LIVE_VALUE'] = 'second'
        self.second_value = self.live_value.get()

    async def then_both_reads_should_return_the_actual_value(self):
        assert self.first_value == 'first'
        assert self.second_value == 'second'


class LiveEnvParserScenario(vedro.Scenario):
    subject = 'live env applies the parser after substituting placeholders'

    async def given_active_worker_context(self):
        reset_current_env_id()
        vedro.defer(reset_current_env_id)
        _set_context('w1-a1b2', worker_id=3)
        patch_env({'UC_LIVE_PORT': '[[worker_id]]42'})

    async def when_value_is_read_as_int(self):
        self.port = live_env.int('UC_LIVE_PORT').get()

    async def then_parser_should_receive_the_substituted_value(self):
        assert self.port == 342


class LiveEnvLiteralScenario(vedro.Scenario):
    subject = 'live env literal substitutes placeholders in an explicit value'

    async def given_active_worker_context(self):
        reset_current_env_id()
        vedro.defer(reset_current_env_id)
        _set_context('w1-a1b2')

    async def when_literal_value_is_read(self):
        self.value = live_env.literal('db-[[namespace]]/[[worker_id]]').get()

    async def then_placeholders_should_be_substituted(self):
        assert self.value == 'db-w1-a1b2/1'


class LiveEnvDefaultScenario(vedro.Scenario):
    subject = 'live env substitutes placeholders in a default value'

    async def given_active_worker_context(self):
        reset_current_env_id()
        vedro.defer(reset_current_env_id)
        _set_context('w1-a1b2')
        patch_env({'UC_LIVE_MISSING': None})

    async def when_missing_value_is_read_with_default(self):
        self.value = live_env.raw('UC_LIVE_MISSING', default='db-[[namespace]]').get()

    async def then_default_should_be_substituted(self):
        assert self.value == 'db-w1-a1b2'


class LiveEnvServicePlaceholderScenario(vedro.Scenario):
    subject = 'live env substitutes service names using the current environment'

    async def given_active_worker_context(self):
        reset_current_env_id()
        vedro.defer(reset_current_env_id)
        set_current_env_context(CurrentEnvContext(
            env_id='w1-a1b2',
            env=Environment(
                Service('db'),
                Service('redis'),
                description='env-a',
            ),
            worker_id=1,
            workers_total=4,
            namespace='w1-a1b2',
            run_id='run-123',
        ))
        patch_env({'UC_LIVE_SERVICES': 'db=[[db]];redis=[[redis]]'})

    async def when_value_with_service_placeholders_is_read(self):
        self.value = live_env.raw('UC_LIVE_SERVICES').get()

    async def then_service_placeholders_should_be_namespaced(self):
        assert self.value == 'db=db-w1-a1b2;redis=redis-w1-a1b2'
