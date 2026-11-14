import vedro
import vedro.plugins.temp_keeper as temp_keeper

from uber_compose.core.constants import cleanup_log_files


class Scenario(vedro.Scenario):
    subject = 'cleanup startup logs when files count exceeds limit'

    def given_log_directory_with_more_files_than_limit(self):
        self.directory = temp_keeper.create_tmp_dir()
        self.keep = self.directory / 'current.log'
        self.keep.write_text('current')
        for index in range(11):
            (self.directory / f'old-{index}.log').write_text('old')

    def when_cleanup_is_called(self):
        cleanup_log_files(self.keep, limit=10, keep=self.keep)

    def then_all_old_files_should_be_removed(self):
        assert sorted(path.name for path in self.directory.iterdir()) == ['current.log']


class BelowLimitScenario(vedro.Scenario):
    subject = 'cleanup startup logs keeps files when count does not exceed limit'

    def given_log_directory_with_files_within_limit(self):
        self.directory = temp_keeper.create_tmp_dir()
        self.keep = self.directory / 'current.log'
        self.keep.write_text('current')
        for index in range(10):
            (self.directory / f'old-{index}.log').write_text('old')

    def when_cleanup_is_called(self):
        cleanup_log_files(self.keep, limit=10, keep=self.keep)

    def then_all_files_should_stay(self):
        assert len(list(self.directory.iterdir())) == 11
