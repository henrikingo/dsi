"""
Unit tests for `post_run_check.py`.
"""
import os
import unittest
import shutil

from mock import patch
from nose.tools import nottest

from common.utils import mkdir_p, touch
from evergreen.history import History
from test_lib.comparator_utils import ANY_IN_STRING
from test_lib.fixture_files import FixtureFiles
import post_run_check

FIXTURE_FILES = FixtureFiles(os.path.dirname(__file__))


class TestPostRunCheck(unittest.TestCase):
    """Test suite."""

    def cleanup(self):
        """ common clean up code. It is called from both setup and teardown to be sure to be sure.
        """
        self.core_file = os.path.join(FIXTURE_FILES.fixture_dir_path, 'core_workloads_reports',
                                      'test_id', 'mongod.0', 'core.file')
        if os.path.exists(self.core_file):
            os.remove(self.core_file)

        self.reports_path = FIXTURE_FILES.fixture_file_path('reports')
        self.fixtures_path = os.path.dirname(self.reports_path)
        shutil.rmtree(self.reports_path, ignore_errors=True)
        mkdir_p(self.reports_path)

    def setUp(self):
        self.cleanup()

    def tearDown(self):
        shutil.rmtree(os.path.join(FIXTURE_FILES.fixture_dir_path, 'cores'), ignore_errors=True)
        shutil.rmtree(self.reports_path, ignore_errors=True)

    @staticmethod
    def _get_history():
        """
        #Return delayed_trigger_core_workloads_wt.history.json as a History object.
        """
        history = History(
            FIXTURE_FILES.load_json_file('delayed_trigger_core_workloads_wt.history.json'))
        return history

    @staticmethod
    def _get_tag_history():
        """
        Return linux-standalone.core_workloads_WT.tags.json as a History object.
        """
        tag_history = History(
            FIXTURE_FILES.load_json_file('linux-standalone.core_workloads_WT.tags.json'))
        return tag_history

    @patch('util._get_history', autospec=True)
    @patch('util._get_tag_history', autospec=True)
    @patch('util.get_task_id', autospec=True)
    def test_post_run_check_ftdc(self, mock_task_id, mock_tag, mock_history):
        """
        Runs the full post run check with FTDC resource checks.
        """
        mock_task_id.return_value = 'sys_perf_linux_standalone_core_workloads_WT_0ff97139df609ae1847da9bfb25c35d209e0936e_16_03_17_21_32_43'  #  pylint: disable=line-too-long
        mock_tag.return_value = self._get_tag_history()
        mock_history.return_value = self._get_history()

        arg_string = \
            "--rev 0ff97139df609ae1847da9bfb25c35d209e0936e " \
            "--refTag 3.2.1-Baseline " \
            "--overrideFile {0}/system_perf_override.json " \
            "--reports-analysis {0}/core_workloads_reports " \
            "--project_id sys-perf --task_name core_workloads_WT --variant linux-standalone " \
            "--report-file {0}/report_ftdc.json --out-file /dev/null".format(
                FIXTURE_FILES.fixture_dir_path)
        post_run_check.main(arg_string.split(" "))
        self.assertTrue(
            FIXTURE_FILES.json_files_equal("report_ftdc.json",
                                           "post_run_check_ftdc.report.json.ok"))
        os.remove(FIXTURE_FILES.fixture_file_path("report_ftdc.json"))

    @patch('util._get_history', autospec=True)
    @patch('util._get_tag_history', autospec=True)
    @patch('util.get_task_id', autospec=True)
    @patch('ftdc_analysis.resource_rules', autospec=True)
    def test_max_thread_level(self, mock_resource_rules, mock_task_id, mock_tag, mock_history):
        """
        Checks that the max_thread_level is calculated correctly,
        by summing up the max_thread_levels for all tests in the task.
        """

        mock_task_id.return_value = 'sys_perf_linux_standalone_core_workloads_WT_0ff97139df609ae1847da9bfb25c35d209e0936e_16_03_17_21_32_43'  #  pylint: disable=line-too-long
        mock_tag.return_value = self._get_tag_history()
        mock_history.return_value = self._get_history()
        mock_resource_rules.return_value = {
            'status': 'pass',
            'end': 1,
            'log_raw': '\nPassed resource sanity checks.',
            'exit_code': 0,
            'start': 0,
            'test_file': 'resource_sanity_checks'
        }

        arg_string = \
            "--rev 0ff97139df609ae1847da9bfb25c35d209e0936e " \
            "--refTag 3.2.1-Baseline " \
            "--overrideFile {0}/system_perf_override.json " \
            "--reports-analysis {0}/core_workloads_reports " \
            "--project_id sys-perf --task_name core_workloads_WT --variant linux-standalone " \
            "--report-file {0}/report_ftdc.json --out-file /dev/null".format(
                FIXTURE_FILES.fixture_dir_path)
        post_run_check.main(arg_string.split(" "))
        mock_resource_rules.assert_called_once_with("{}/core_workloads_reports".format(
            FIXTURE_FILES.fixture_dir_path), 'sys-perf', 'linux-standalone',
                                                    {'max_thread_level': 419}, None)
        os.remove(FIXTURE_FILES.fixture_file_path("report_ftdc.json"))

    @patch('util._get_history', autospec=True)
    @patch('util._get_tag_history', autospec=True)
    @patch('util.get_task_id', autospec=True)
    def test_post_run_check_core_fail(self, mock_task_id, mock_tag, mock_history):
        """
        Runs the full post run check with FTDC resource and core file failure checks.
        """
        mock_task_id.return_value = 'sys_perf_linux_standalone_core_workloads_WT_0ff97139df609ae1847da9bfb25c35d209e0936e_16_03_17_21_32_43'  #  pylint: disable=line-too-long
        mock_tag.return_value = self._get_tag_history()
        mock_history.return_value = self._get_history()

        arg_string = \
            "--rev 0ff97139df609ae1847da9bfb25c35d209e0936e " \
            "--refTag 3.2.1-Baseline " \
            "--overrideFile {0}/system_perf_override.json " \
            "--reports-analysis {0}/core_workloads_reports " \
            "--project_id sys-perf --task_name core_workloads_WT --variant linux-standalone " \
            "--report-file {0}/report_core.json --out-file /dev/null".format(
                FIXTURE_FILES.fixture_dir_path)

        mkdir_p(os.path.dirname(self.core_file))
        touch(self.core_file)
        post_run_check.main(arg_string.split(" "))
        self.assertTrue(
            FIXTURE_FILES.json_files_equal("report_core.json",
                                           "post_run_check_core_fail.report.json.ok"))
        os.remove(FIXTURE_FILES.fixture_file_path("report_core.json"))
        os.remove(self.core_file)

    @patch('util._get_history', autospec=True)
    @patch('util._get_tag_history', autospec=True)
    @patch('util.get_task_id', autospec=True)
    def test_post_run_check(self, mock_task_id, mock_tag, mock_history):
        """
        Runs the full post run check without FTDC resource checks.
        """
        mock_task_id.return_value = 'sys_perf_linux_standalone_core_workloads_WT_0ff97139df609ae1847da9bfb25c35d209e0936e_16_03_17_21_32_43'  #  pylint: disable=line-too-long
        mock_tag.return_value = self._get_tag_history()
        mock_history.return_value = self._get_history()

        arg_string = \
            "--rev 0ff97139df609ae1847da9bfb25c35d209e0936e " \
            "--refTag 3.2.1-Baseline " \
            "--overrideFile {0}/system_perf_override.json " \
            "--project_id sys-perf --task_name core_workloads_WT --variant linux-standalone " \
            "--report-file {0}/report.json --out-file /dev/null".format(FIXTURE_FILES.fixture_dir_path)
        post_run_check.main(arg_string.split(" "))
        self.assertTrue(
            FIXTURE_FILES.json_files_equal("report.json", "post_run_check.report.json.ok"))
        os.remove(FIXTURE_FILES.fixture_file_path("report.json"))

    def test_skip_files(self):
        """
        test check_core_file_exists skips listdir on files (and avoids an exception).
        """

        core_path = FIXTURE_FILES.fixture_file_path('cores')
        shutil.rmtree(core_path, ignore_errors=True)
        mkdir_p(core_path)

        # matching directories but no core files
        log_filename = os.path.join(core_path, 'infrastructure_provisioning.out.yml')
        touch(log_filename)

        try:
            post_run_check.check_core_file_exists(core_path), [{
                'status': 'pass',
                'start': 0,
                'test_file': 'core.test_id.mongod.0',
                'log_raw': '\nNo core files found',
                'exit_code': 0
            }]
        except:
            self.fail("check_core_file_exists() raised Exception!")

    def test_check_core_file_exists(self):
        """
        test check_core_file_exists directly.
        """

        def check_failures(results, expected):
            """ helper to wrap called checks
            :type expected: list
            :type results: list
            :param expected: array containing [expexted dict result, filenames*]
            :param results: array of dict results
            """
            self.assertEquals(len(results), len(expected))
            for i, result in enumerate(results):
                current = expected[i][0]
                self.assertDictContainsSubset(current, result)
                for filename in expected[i][1:]:
                    self.assertIn(os.path.basename(filename), result['log_raw'])

        core_path = FIXTURE_FILES.fixture_file_path('cores')
        shutil.rmtree(core_path, ignore_errors=True)
        mkdir_p(core_path)

        # no matching directories
        self.assertEquals(post_run_check.check_core_file_exists(core_path), [])

        # matching directories but no core files
        log_filename = os.path.join(core_path, 'test_id', 'mongod.0', 'mongod.log')
        mkdir_p(os.path.dirname(log_filename))
        touch(log_filename)

        self.assertEquals(
            post_run_check.check_core_file_exists(core_path), [{
                'status': 'pass',
                'start': 0,
                'test_file': 'core.test_id.mongod.0',
                'log_raw': '\nNo core files found',
                'exit_code': 0
            }])

        # mongod
        core_path = FIXTURE_FILES.fixture_file_path('cores')
        shutil.rmtree(core_path, ignore_errors=True)
        mkdir_p(core_path)

        # single matching mongod core file and default pattern
        core_filename = os.path.join(core_path, 'test_id', 'mongod.0', 'core.test.mongod.0')
        mkdir_p(os.path.dirname(core_filename))
        touch(core_filename)

        expected = [[{
            'status': 'fail',
            'start': 0,
            'test_file': 'core.test_id.mongod.0',
            'exit_code': 1
        }, core_filename]]
        check_failures(post_run_check.check_core_file_exists(core_path), expected)
        check_failures(post_run_check.check_core_file_exists(core_path, pattern="core.*"), expected)

        # single mongos match
        core_path = FIXTURE_FILES.fixture_file_path('cores')
        shutil.rmtree(core_path, ignore_errors=True)
        mkdir_p(core_path)

        core_filename = os.path.join(core_path, 'test_id', 'mongos.0', 'core.test.mongos.0')
        mkdir_p(os.path.dirname(core_filename))
        touch(core_filename)

        expected = [[{
            'status': 'fail',
            'start': 0,
            'test_file': 'core.test_id.mongos.0',
            'exit_code': 1
        }, core_filename]]
        check_failures(post_run_check.check_core_file_exists(core_path), expected)

        # single matching configsvr
        core_path = FIXTURE_FILES.fixture_file_path('cores')
        shutil.rmtree(core_path, ignore_errors=True)
        mkdir_p(core_path)

        # single matching core file and default pattern
        core_filename = os.path.join(core_path, 'test_id', 'configsvr.0', 'core.test.configsvr.0')
        mkdir_p(os.path.dirname(core_filename))
        touch(core_filename)

        expected = [[{
            'status': 'fail',
            'start': 0,
            'test_file': 'core.test_id.configsvr.0',
            'exit_code': 1
        }, core_filename]]
        check_failures(post_run_check.check_core_file_exists(core_path), expected)

        # multiple mongod
        core_path = FIXTURE_FILES.fixture_file_path('cores')
        shutil.rmtree(core_path, ignore_errors=True)
        mkdir_p(core_path)

        # single matching core file and default pattern
        core_filename = os.path.join(core_path, 'test_id', 'mongod.0', 'core.test.mongod.0')
        mkdir_p(os.path.dirname(core_filename))
        touch(core_filename)
        core_filename_1 = os.path.join(core_path, 'test_id', 'mongod.0', 'core.test.mongod.1')
        mkdir_p(os.path.dirname(core_filename_1))
        touch(core_filename_1)

        expected = [[{
            'status': 'fail',
            'start': 0,
            'test_file': 'core.test_id.mongod.0',
            'exit_code': 1
        }, core_filename, core_filename_1]]
        check_failures(post_run_check.check_core_file_exists(core_path), expected)

        # combinations
        core_path = FIXTURE_FILES.fixture_file_path('cores')
        shutil.rmtree(core_path, ignore_errors=True)
        mkdir_p(core_path)

        core_filename = os.path.join(core_path, 'test_id', 'mongod.0', 'core.test.mongod.0')
        mkdir_p(os.path.dirname(core_filename))
        touch(core_filename)

        core_filename_1 = os.path.join(core_path, 'test_id', 'mongod.1', 'core.test.mongod.1')
        mkdir_p(os.path.dirname(core_filename_1))
        touch(core_filename_1)

        core_filename_2 = os.path.join(core_path, 'test_id', 'mongos.0', 'core.test.mongos.2')
        mkdir_p(os.path.dirname(core_filename_2))
        touch(core_filename_2)

        core_filename_3 = os.path.join(core_path, 'test_id', 'mongos.0', 'core.test.mongos.3')
        mkdir_p(os.path.dirname(core_filename_3))
        touch(core_filename_3)

        core_filename_4 = os.path.join(core_path, 'test_id', 'configsvr.0', 'core.test.configsvr.4')
        mkdir_p(os.path.dirname(core_filename_4))
        touch(core_filename_4)

        core_filename_5 = os.path.join(core_path, 'test_id', 'configsvr.0', 'core.test.configsvr.5')
        mkdir_p(os.path.dirname(core_filename_5))
        touch(core_filename_5)

        expected = [[
            {
                'status': 'fail',
                'start': 0,
                'test_file': 'core.test_id.configsvr.0',
                'exit_code': 1
            },
            core_filename_4,
            core_filename_5,
        ], [{
            'status': 'fail',
            'start': 0,
            'test_file': 'core.test_id.mongod.0',
            'exit_code': 1
        }, core_filename], [{
            'status': 'fail',
            'start': 0,
            'test_file': 'core.test_id.mongod.1',
            'exit_code': 1
        }, core_filename_1], [{
            'status': 'fail',
            'start': 0,
            'test_file': 'core.test_id.mongos.0',
            'exit_code': 1
        }, core_filename_3]]
        results = post_run_check.check_core_file_exists(core_path)
        check_failures(results, expected)

        # repeat the test above but with only one failure
        os.remove(core_filename_4)
        os.remove(core_filename_5)

        expected = [[{
            'status': 'pass',
            'start': 0,
            'test_file': 'core.test_id.configsvr.0',
            'exit_code': 0
        }], [{
            'status': 'fail',
            'start': 0,
            'test_file': 'core.test_id.mongod.0',
            'exit_code': 1
        }, core_filename], [{
            'status': 'fail',
            'start': 0,
            'test_file': 'core.test_id.mongod.1',
            'exit_code': 1
        }, core_filename_1], [{
            'status': 'fail',
            'start': 0,
            'test_file': 'core.test_id.mongos.0',
            'exit_code': 1
        }, core_filename_3]]
        results = post_run_check.check_core_file_exists(core_path)
        check_failures(results, expected)

        shutil.rmtree(core_path, ignore_errors=True)

    @nottest
    def when_check_test_output_files(self, case):
        """
        :param case: contains given/then conditions for behavior of _perform_exec

        Example:

            'given': {
                # params given to _perform_exec
                'command': 'cowsay HellowWorld',
                'max_timeout_ms': 750,
                'no_output_timeout_ms': 20,
                # mock _stream behavior
                'ssh_interrupt_after_ms': 5,
                'with_output': False,
                # (was exist status ready, actual exit status)
                'and_exit_status': (True, 0),
            },
            'then': {
                # asserted output of _perform_exec
                'exit_status': 0,
                'did_timeout': False,
                'time_taken_seconds': ANY
            }
        """

        current_path = os.getcwd()
        os.chdir(self.fixtures_path)

        given = case['given']
        then = case['then']

        return_value = post_run_check.check_test_output_files(given['reports_dir_path'])
        self.assertItemsEqual(return_value, then)

        os.chdir(current_path)

    def test_check_exit_status_no_files(self):
        """
        test exit status check with no files.
        """

        self.when_check_test_output_files({
            'given': {
                'reports_dir_path': os.path.basename(self.reports_path)
            },
            'then': []
        })

    def test_check_exit_status_no_match(self):
        """
        test exit status check with no matching file names.
        """

        filename = os.path.join(self.reports_path, 'foo', 'buzz.bar')
        mkdir_p(os.path.dirname(filename))
        touch(filename)
        self.when_check_test_output_files({
            'given': {
                'reports_dir_path': self.reports_path
            },
            'then': []
        })

    def test_check_exit_status_empty(self):
        """
        test exit status check with matching file name and no content (this is an error).
        """

        reports_path = os.path.basename(self.reports_path)
        filename = os.path.join(reports_path, 'foo', 'test_output.log')
        full_filename = os.path.join(self.fixtures_path, filename)
        mkdir_p(os.path.dirname(full_filename))
        touch(full_filename)
        self.when_check_test_output_files({
            'given': {
                'reports_dir_path': reports_path
            },
            'then': [{
                'exit_code':
                    1,
                'log_raw':
                    ANY_IN_STRING("Command Failed: status=1 message=Unknown Error: empty file"),
                'start':
                    0,
                'status':
                    'fail',
                'test_file':
                    'foo test_output.log'
            }]
        })

    def test_check_exit_status_0(self):
        """
        test exit status check with matching file name and exit status 0.
        """

        reports_path = os.path.basename(self.reports_path)
        filename = os.path.join(reports_path, 'foo', 'test_output.log')
        full_filename = os.path.join(self.fixtures_path, filename)
        mkdir_p(os.path.dirname(full_filename))
        touch(full_filename)

        with open(full_filename, 'w+') as file_handle:
            file_handle.write("exit_status: 0")

        self.when_check_test_output_files({
            'given': {
                'reports_dir_path': reports_path
            },
            'then': [{
                'exit_code': 0,
                'start': 0,
                'status': 'pass',
                'test_file': 'foo test_output.log',
                'log_raw': "Command Succeeded: status=0",
            }]
        })

    def test_check_exit_status_message(self):
        """
        test exit status check with matching file name and exit status 0.
        """

        reports_path = os.path.basename(self.reports_path)
        filename = os.path.join(reports_path, 'foo', 'test_output.log')
        full_filename = os.path.join(self.fixtures_path, filename)
        mkdir_p(os.path.dirname(full_filename))
        touch(full_filename)

        with open(full_filename, 'w+') as file_handle:
            file_handle.write("exit_status: 0 this is a message")

        self.when_check_test_output_files({
            'given': {
                'reports_dir_path': reports_path
            },
            'then': [{
                'exit_code': 0,
                'start': 0,
                'status': 'pass',
                'log_raw': 'Command Succeeded: status=0 message=this is a message',
                'test_file': 'foo test_output.log'
            }]
        })

    def test_check_exit_status_2(self):
        """
        test exit status check with matching file name and exit status 2.
        """

        reports_path = os.path.basename(self.reports_path)
        filename = os.path.join(reports_path, 'foo', 'test_output.log')
        full_filename = os.path.join(self.fixtures_path, filename)
        mkdir_p(os.path.dirname(full_filename))
        touch(full_filename)
        with open(full_filename, 'w+') as file_handle:
            file_handle.write("exit_status: 2 test")

        self.when_check_test_output_files({
            'given': {
                'reports_dir_path': reports_path
            },
            'then': [{
                'exit_code': 2,
                'log_raw': 'Command Failed: status=2 message=test',
                'start': 0,
                'status': 'fail',
                'test_file': 'foo test_output.log'
            }]
        })

    def test_check_exit_status_multiple(self):
        """
        test exit status check with matching files and various status.
        """

        reports_path = os.path.basename(self.reports_path)
        foo_filename = os.path.join(reports_path, 'foo', 'test_output.log')
        full_filename = os.path.join(self.fixtures_path, foo_filename)
        mkdir_p(os.path.dirname(full_filename))
        touch(full_filename)

        bar_filename = os.path.join(reports_path, 'bar', 'test_output.log')
        full_filename = os.path.join(self.fixtures_path, bar_filename)
        mkdir_p(os.path.dirname(full_filename))
        touch(full_filename)

        with open(full_filename, 'w+') as file_handle:
            file_handle.write("exit_status: 2 test")

        buz_filename = os.path.join(reports_path, 'buz', 'test_output.log')
        full_filename = os.path.join(self.fixtures_path, buz_filename)
        mkdir_p(os.path.dirname(full_filename))
        touch(full_filename)

        with open(full_filename, 'w+') as file_handle:
            file_handle.write("exit_status: 0")

        self.when_check_test_output_files({
            'given': {
                'reports_dir_path': reports_path
            },
            'then': [{
                'exit_code': 1,
                'log_raw': ANY_IN_STRING("Unknown Error: empty file"),
                'start': 0,
                'status': 'fail',
                'test_file': 'foo test_output.log'
            }, {
                'exit_code': 2,
                'log_raw': ANY_IN_STRING("message=test"),
                'start': 0,
                'status': 'fail',
                'test_file': 'bar test_output.log'
            }, {
                'exit_code': 0,
                'start': 0,
                'status': 'pass',
                'test_file': 'buz test_output.log',
                'log_raw': "Command Succeeded: status=0",
            }]
        })


if __name__ == '__main__':
    unittest.main()
