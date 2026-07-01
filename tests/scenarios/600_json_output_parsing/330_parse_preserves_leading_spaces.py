import vedro
from d42 import schema

from uber_compose.vedro_plugin.base_structures.common_json_cli import JsonParser


class Scenario(vedro.Scenario):
    subject = 'parse_output_to_json preserves leading spaces in CLI help lines'

    def given_parser_with_dict_output(self):
        self.parser = JsonParser(dict_output=True)

    def given_cli_help_like_logs(self):
        self.logs = (
            b'usage: reviews-trust-cli [<flags>] [<args> ...]\n'
            b'Cli interface for the service.\n'
            b'    help [<flags>] [<args> ...]\n'
            b'        Show help.\n'
            b'    migrate db --db-dsn=DB-DSN [<flags>] [<args> ...]\n'
            b'        Apply migrations to PG storage.\n'
        )

    def when_user_parses_logs(self):
        self.stdout, self.stderr = self.parser.parse_output_to_json(self.logs)

    def then_it_should_preserve_leading_spaces_in_raw_lines(self):
        assert self.stdout == schema.list([
            schema.dict({'raw': schema.str('usage: reviews-trust-cli [<flags>] [<args> ...]')}),
            schema.dict({'raw': schema.str('Cli interface for the service.')}),
            schema.dict({'raw': schema.str('    help [<flags>] [<args> ...]')}),
            schema.dict({'raw': schema.str('        Show help.')}),
            schema.dict({'raw': schema.str('    migrate db --db-dsn=DB-DSN [<flags>] [<args> ...]')}),
            schema.dict({'raw': schema.str('        Apply migrations to PG storage.')}),
        ])

    def then_it_should_treat_help_lines_as_errors(self):
        assert self.stderr == self.stdout
