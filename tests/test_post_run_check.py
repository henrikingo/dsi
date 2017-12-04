"""
Unit tests for `post_run_check.py`.
"""
import os
import unittest
import errno
import shutil

import post_run_check
from tests import test_utils


def touch(filename):
    """ create an empty file (like shell touch command). It will not
    create directories
    :type filename: string the full path to the filename
    """
    open(filename, 'a').close()


class TestPostRunCheck(unittest.TestCase):
    """Test suite."""

    def cleanup(self):
        """ common clean up code. It is called from both setup and teardown to be sure to be sure.
        """
        self.core_file = os.path.join(test_utils.FIXTURE_DIR_PATH,
                                      'core_workloads_reports/mongod.0/'
                                      'core.file')
        if os.path.exists(self.core_file):
            os.remove(self.core_file)

    def setUp(self):
        self.cleanup()

    def tearDown(self):
        self.cleanup()

    def test_post_run_check_ftdc(self):
        """
        Runs the full post run check with FTDC resource checks.
        """
        arg_string = \
            "--rev 0ff97139df609ae1847da9bfb25c35d209e0936e -f " \
            "{0}/delayed_trigger_core_workloads_wt.history.json " \
            "-t {0}/linux-standalone.core_workloads_WT.tags.json --refTag 3.2.1-Baseline " \
            "--overrideFile {0}/system_perf_override.json " \
            "--reports-analysis {0}/core_workloads_reports " \
            "--project_id sys-perf --task_name core_workloads_WT --variant linux-standalone " \
            "--report-file {0}/report_ftdc.json --out-file /dev/null".format(
                test_utils.FIXTURE_DIR_PATH)
        post_run_check.main(arg_string.split(" "))
        self.assertTrue(
            test_utils.eq_fixture_json_files("report_ftdc.json",
                                             "post_run_check_ftdc.report.json.ok"))
        os.remove(test_utils.fixture_file_path("report_ftdc.json"))

    def test_post_run_check_core_fail(self):
        """
        Runs the full post run check with FTDC resource and core file failure checks.
        """
        arg_string = \
            "--rev 0ff97139df609ae1847da9bfb25c35d209e0936e -f " \
            "{0}/delayed_trigger_core_workloads_wt.history.json " \
            "-t {0}/linux-standalone.core_workloads_WT.tags.json --refTag 3.2.1-Baseline " \
            "--overrideFile {0}/system_perf_override.json " \
            "--reports-analysis {0}/core_workloads_reports " \
            "--project_id sys-perf --task_name core_workloads_WT --variant linux-standalone " \
            "--report-file {0}/report_ftdc.json --out-file /dev/null".format(
                test_utils.FIXTURE_DIR_PATH)

        touch(self.core_file)
        post_run_check.main(arg_string.split(" "))
        self.assertTrue(
            test_utils.eq_fixture_json_files("report_ftdc.json",
                                             "post_run_check_core_fail.report.json.ok"))
        os.remove(test_utils.fixture_file_path("report_ftdc.json"))
        os.remove(self.core_file)

    def test_post_run_check(self):
        """
        Runs the full post run check without FTDC resource checks.
        """
        arg_string = \
            "--rev 0ff97139df609ae1847da9bfb25c35d209e0936e -f " \
            "{0}/delayed_trigger_core_workloads_wt.history.json " \
            "-t {0}/linux-standalone.core_workloads_WT.tags.json --refTag 3.2.1-Baseline " \
            "--overrideFile {0}/system_perf_override.json " \
            "--project_id sys-perf --task_name core_workloads_WT --variant linux-standalone " \
            "--report-file {0}/report.json --out-file /dev/null".format(test_utils.FIXTURE_DIR_PATH)
        post_run_check.main(arg_string.split(" "))
        self.assertTrue(
            test_utils.eq_fixture_json_files("report.json", "post_run_check.report.json.ok"))
        os.remove(test_utils.fixture_file_path("report.json"))

    # pylint: disable=too-many-statements
    def test_check_core_file_exists(self):
        """
        test check_core_file_exists directly.
        """

        def mkdir_p(path):
            """ make the directory and all missing parents (like mkdir -p)
            :type path: string the directory path
            """
            try:
                os.makedirs(path)
            except OSError as exc:  # Python >2.5
                if exc.errno == errno.EEXIST and os.path.isdir(path):
                    pass
                else:
                    raise

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

        core_path = test_utils.fixture_file_path('cores')
        shutil.rmtree(core_path, ignore_errors=True)
        mkdir_p(core_path)

        # no matching directories
        self.assertEquals(post_run_check.check_core_file_exists(core_path), [])

        # matching directories but no core files
        log_filename = os.path.join(core_path, 'mongod.0', 'mongod.log')
        mkdir_p(os.path.dirname(log_filename))
        touch(log_filename)

        self.assertEquals(
            post_run_check.check_core_file_exists(core_path), [{
                'status': 'pass',
                'start': 0,
                'test_file': 'core.mongod.0',
                'log_raw': '\nNo core files found',
                'exit_code': 0
            }])

        # mongod
        core_path = test_utils.fixture_file_path('cores')
        shutil.rmtree(core_path, ignore_errors=True)
        mkdir_p(core_path)

        # single matching mongod core file and default pattern
        core_filename = os.path.join(core_path, 'mongod.0', 'core.test.mongod.0')
        mkdir_p(os.path.dirname(core_filename))
        touch(core_filename)

        expected = [[{
            'status': 'fail',
            'start': 0,
            'test_file': 'core.mongod.0',
            'exit_code': 1
        }, core_filename]]
        check_failures(post_run_check.check_core_file_exists(core_path), expected)
        check_failures(post_run_check.check_core_file_exists(core_path, pattern="core.*"), expected)

        # single mongos match
        core_path = test_utils.fixture_file_path('cores')
        shutil.rmtree(core_path, ignore_errors=True)
        mkdir_p(core_path)

        core_filename = os.path.join(core_path, 'mongos.0', 'core.test.mongos.0')
        mkdir_p(os.path.dirname(core_filename))
        touch(core_filename)

        expected = [[{
            'status': 'fail',
            'start': 0,
            'test_file': 'core.mongos.0',
            'exit_code': 1
        }, core_filename]]
        check_failures(post_run_check.check_core_file_exists(core_path), expected)

        # single matching configsvr
        core_path = test_utils.fixture_file_path('cores')
        shutil.rmtree(core_path, ignore_errors=True)
        mkdir_p(core_path)

        # single matching core file and default pattern
        core_filename = os.path.join(core_path, 'configsvr.0', 'core.test.configsvr.0')
        mkdir_p(os.path.dirname(core_filename))
        touch(core_filename)

        expected = [[{
            'status': 'fail',
            'start': 0,
            'test_file': 'core.configsvr.0',
            'exit_code': 1
        }, core_filename]]
        check_failures(post_run_check.check_core_file_exists(core_path), expected)

        # multiple mongod
        core_path = test_utils.fixture_file_path('cores')
        shutil.rmtree(core_path, ignore_errors=True)
        mkdir_p(core_path)

        # single matching core file and default pattern
        core_filename = os.path.join(core_path, 'mongod.0', 'core.test.mongod.0')
        mkdir_p(os.path.dirname(core_filename))
        touch(core_filename)
        core_filename_1 = os.path.join(core_path, 'mongod.0', 'core.test.mongod.1')
        mkdir_p(os.path.dirname(core_filename_1))
        touch(core_filename_1)

        expected = [[{
            'status': 'fail',
            'start': 0,
            'test_file': 'core.mongod.0',
            'exit_code': 1
        }, core_filename, core_filename_1]]
        check_failures(post_run_check.check_core_file_exists(core_path), expected)

        # combinations
        core_path = test_utils.fixture_file_path('cores')
        shutil.rmtree(core_path, ignore_errors=True)
        mkdir_p(core_path)

        core_filename = os.path.join(core_path, 'mongod.0', 'core.test.mongod.0')
        mkdir_p(os.path.dirname(core_filename))
        touch(core_filename)

        core_filename_1 = os.path.join(core_path, 'mongod.1', 'core.test.mongod.1')
        mkdir_p(os.path.dirname(core_filename_1))
        touch(core_filename_1)

        core_filename_2 = os.path.join(core_path, 'mongos.0', 'core.test.mongos.2')
        mkdir_p(os.path.dirname(core_filename_2))
        touch(core_filename_2)

        core_filename_3 = os.path.join(core_path, 'mongos.0', 'core.test.mongos.3')
        mkdir_p(os.path.dirname(core_filename_3))
        touch(core_filename_3)

        core_filename_4 = os.path.join(core_path, 'configsvr.0', 'core.test.configsvr.4')
        mkdir_p(os.path.dirname(core_filename_4))
        touch(core_filename_4)

        core_filename_5 = os.path.join(core_path, 'configsvr.0', 'core.test.configsvr.5')
        mkdir_p(os.path.dirname(core_filename_5))
        touch(core_filename_5)

        expected = [[
            {
                'status': 'fail',
                'start': 0,
                'test_file': 'core.configsvr.0',
                'exit_code': 1
            },
            core_filename_4,
            core_filename_5,
        ], [{
            'status': 'fail',
            'start': 0,
            'test_file': 'core.mongod.0',
            'exit_code': 1
        }, core_filename], [{
            'status': 'fail',
            'start': 0,
            'test_file': 'core.mongod.1',
            'exit_code': 1
        }, core_filename_1], [{
            'status': 'fail',
            'start': 0,
            'test_file': 'core.mongos.0',
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
            'test_file': 'core.configsvr.0',
            'exit_code': 0
        }], [{
            'status': 'fail',
            'start': 0,
            'test_file': 'core.mongod.0',
            'exit_code': 1
        }, core_filename], [{
            'status': 'fail',
            'start': 0,
            'test_file': 'core.mongod.1',
            'exit_code': 1
        }, core_filename_1], [{
            'status': 'fail',
            'start': 0,
            'test_file': 'core.mongos.0',
            'exit_code': 1
        }, core_filename_3]]
        results = post_run_check.check_core_file_exists(core_path)
        check_failures(results, expected)

        shutil.rmtree(core_path, ignore_errors=True)


if __name__ == '__main__':
    unittest.main()
