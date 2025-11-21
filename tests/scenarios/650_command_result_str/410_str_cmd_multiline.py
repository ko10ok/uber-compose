import vedro
from d42 import schema

from uber_compose.vedro_plugin.base_structures.common_json_cli import CommandResult


class Scenario(vedro.Scenario):
    subject = 'CommandResult.__str__ with multi-line cmd'

    def given_command_result_with_multiline_cmd(self):
        self.result = CommandResult(
            stdout=['log'],
            stderr=[],
            cmd='echo "line1"\necho "line2"\necho "line3"',
            env={'VAR': 'value'}
        )

    def when_user_converts_to_string(self):
        self.result_str = str(self.result)

    def then_it_should_match_expected_format(self):
        expected = """CommandResult(
    stdout = ['log'],
    stderr = [],
    cmd = '''
          echo "line1"
          echo "line2"
          echo "line3"
          ''',
    env = {'VAR': 'value'}
)"""
        assert self.result_str == schema.str % expected
