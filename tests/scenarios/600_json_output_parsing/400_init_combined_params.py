import vedro
from d42 import schema

from uber_compose.vedro_plugin.base_structures.common_json_cli import JsonParser


class Scenario(vedro.Scenario):
    subject = 'JsonParser initialization with combined parameters'

    def given_parser_with_multiple_params(self):
        self.parser = JsonParser(
            log_level_key='severity',
            stderr_log_levels=['error', 'critical'],
            full_stdout=False,
            dict_output=True,
            skips=['health']
        )

    def given_complex_logs(self):
        self.logs = b'''{"severity": "info", "msg": "Starting"}
{"severity": "debug", "msg": "health check OK"}
{"severity": "error", "msg": "Failed to connect"}
{"severity": "info", "msg": "Retrying"}'''

    def when_user_parses_logs(self):
        self.stdout, self.stderr = self.parser.parse_output_to_json(self.logs)

    def then_stdout_should_contain_only_non_errors(self):
        # full_stdout=False, so error NOT in stdout
        # Only 3 lines: info, skipped health check, info
        assert self.stdout == schema.list([
            schema.dict({
                'severity': schema.str('info'),
                'msg': schema.str('Starting')
            }),
            schema.dict({
                'raw': schema.str('{"severity": "debug", "msg": "health check OK"}')
            }),
            schema.dict({
                'severity': schema.str('info'),
                'msg': schema.str('Retrying')
            })
        ])

    def then_stderr_should_contain_only_errors(self):
        # Only error level (not debug/info) should be in stderr
        assert self.stderr == schema.list([
            schema.dict({
                'severity': schema.str('error'),
                'msg': schema.str('Failed to connect')
            })
        ])
