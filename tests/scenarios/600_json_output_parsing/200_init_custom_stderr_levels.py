import vedro
from d42 import schema

from uber_compose.vedro_plugin.base_structures.common_json_cli import JsonParser, LogLevels


class Scenario(vedro.Scenario):
    subject = 'JsonParser initialization with custom stderr_log_levels'

    def given_custom_stderr_log_levels(self):
        self.custom_levels = [LogLevels.ERROR, LogLevels.FATAL]

    def when_user_creates_parser_with_custom_levels(self):
        self.parser = JsonParser(stderr_log_levels=self.custom_levels)

    def then_it_should_have_custom_stderr_levels(self):
        assert self.parser.stderr_log_levels == self.custom_levels
        assert LogLevels.WARNING not in self.parser.stderr_log_levels

    def given_logs_with_warnings(self):
        self.logs = b'''{"level": "info", "msg": "Info message"}
{"level": "warning", "msg": "Warning message"}
{"level": "error", "msg": "Error message"}'''

    def when_user_parses_logs_with_custom_parser(self):
        self.stdout, self.stderr = self.parser.parse_output_to_json(self.logs)

    def then_it_should_not_treat_warning_as_error(self):
        # With custom levels, warning should not be in stderr
        assert self.stderr == schema.list([
            schema.str % '{"level": "error", "msg": "Error message"}'
        ])

    def then_it_should_have_all_in_stdout(self):
        assert self.stdout == schema.list(schema.str).len(3)
