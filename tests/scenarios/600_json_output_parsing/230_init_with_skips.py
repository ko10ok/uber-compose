import vedro
from d42 import schema

from uber_compose.vedro_plugin.base_structures.common_json_cli import JsonParser


class Scenario(vedro.Scenario):
    subject = 'JsonParser initialization with skips parameter'

    def given_parser_with_skips(self):
        self.parser = JsonParser(skips=['health check', 'keepalive', 'connection error'])

    def given_logs_with_skippable_lines(self):
        self.logs = b'''{"level": "info", "msg": "Starting service"}
{"level": "debug", "msg": "health check passed"}
Plain text with keepalive skip pattern
{"level": "error", "msg": "Connection failed"}
{"level": "info", "msg": "Processing request"}
{"level": "error", "msg": "Minor connection error detected"}
Unformatted line without skip pattern
{"level": "debug", "msg": "keepalive signal"}'''

    def when_user_parses_logs(self):
        self.stdout, self.stderr = self.parser.parse_output_to_json(self.logs)

    def then_it_should_have_all_lines_in_stdout(self):
        # All 8 lines are in stdout (full_stdout=True by default)
        assert self.stdout == schema.list(schema.str).len(8)

    def then_it_should_have_errors_and_non_json_in_stderr(self):
        # Non-skipped error + non-JSON line without skip pattern should be in stderr
        # Order: error appears first, then non-JSON line
        assert self.stderr == schema.list([
            schema.str % '{"level": "error", "msg": "Connection failed"}',
            schema.str('Unformatted line without skip pattern')
        ])

    def then_stdout_should_match_exact_format(self):
        assert self.stdout == schema.list([
            schema.str % '{"level": "info", "msg": "Starting service"}',                    # Parsed JSON
            schema.str('{"level": "debug", "msg": "health check passed"}'),               # Skipped (raw)
            schema.str('Plain text with keepalive skip pattern'),                         # Skipped (raw)
            schema.str % '{"level": "error", "msg": "Connection failed"}',                  # Parsed JSON
            schema.str % '{"level": "info", "msg": "Processing request"}',                  # Parsed JSON
            schema.str('{"level": "error", "msg": "Minor connection error detected"}'),   # Skipped (raw)
            schema.str('Unformatted line without skip pattern'),                          # Non-JSON (raw)
            schema.str('{"level": "debug", "msg": "keepalive signal"}')                   # Skipped (raw)
        ])
