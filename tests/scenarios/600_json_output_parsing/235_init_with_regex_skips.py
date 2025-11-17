import vedro
from d42 import schema

from uber_compose.vedro_plugin.base_structures.common_json_cli import JsonParser


class Scenario(vedro.Scenario):
    subject = 'JsonParser initialization with skips parameter using regex patterns'

    def given_parser_with_regex_skips(self):
        # Using regex patterns to skip lines
        self.parser = JsonParser(skips=[
            r'health.*check',           # Matches "health check", "health status check", etc.
            r'keepalive\s+signal',      # Matches "keepalive signal" with spaces
            r'connection\s+error\s+\d+' # Matches "connection error" with numbers
        ])

    def given_logs_with_regex_skippable_lines(self):
        self.logs = b'''{"level": "info", "msg": "Starting service"}
{"level": "debug", "msg": "health status check passed"}
Plain text matching keepalive  signal pattern
{"level": "error", "msg": "Connection failed"}
{"level": "info", "msg": "Processing request"}
{"level": "error", "msg": "Minor connection error 503 detected"}
Unformatted line not matching any regex
{"level": "warning", "msg": "connection timeout"}'''

    def when_user_parses_logs(self):
        self.stdout, self.stderr = self.parser.parse_output_to_json(self.logs)

    def then_it_should_have_all_lines_in_stdout(self):
        # All 8 lines are in stdout (full_stdout=True by default)
        assert self.stdout == schema.list(schema.str).len(8)

    def then_it_should_have_errors_and_non_json_in_stderr(self):
        # Non-skipped errors + non-JSON line without matching regex should be in stderr
        assert self.stderr == schema.list([
            schema.str % '{"level": "error", "msg": "Connection failed"}',
            schema.str('Unformatted line not matching any regex'),
            schema.str % '{"level": "warning", "msg": "connection timeout"}'
        ])

    def then_stdout_should_match_exact_format(self):
        # Strict check: parsed JSON lines formatted, skipped/non-JSON lines as raw strings
        assert self.stdout == schema.list([
            schema.str % '{"level": "info", "msg": "Starting service"}',                     # Parsed JSON
            schema.str('{"level": "debug", "msg": "health status check passed"}'),         # Skipped by regex (raw)
            schema.str('Plain text matching keepalive  signal pattern'),                   # Skipped by regex (raw)
            schema.str % '{"level": "error", "msg": "Connection failed"}',                   # Parsed JSON
            schema.str % '{"level": "info", "msg": "Processing request"}',                   # Parsed JSON
            schema.str('{"level": "error", "msg": "Minor connection error 503 detected"}'), # Skipped by regex (raw)
            schema.str('Unformatted line not matching any regex'),                         # Non-JSON (raw)
            schema.str % '{"level": "warning", "msg": "connection timeout"}'                 # Parsed JSON
        ])
