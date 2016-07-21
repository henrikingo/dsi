"""
Unit tests for `post_run_check.py`.
"""

import os
import unittest

import post_run_check
from tests import test_utils

class TestPostRunCheck(unittest.TestCase):
    """Test suite."""

    def test_resource_rules_pass(self):
        """ Specifically test that we get the expected report info for resource sanity checks
        """
        dir_path = '{0}core_workloads_reports'.format(test_utils.FIXTURE_DIR_PATH)
        project = 'sys-perf'
        variant = 'linux-standalone'
        constant_values = {'max_thread_level': 64}
        observed_result = post_run_check.resource_rules(dir_path, project, variant, constant_values)
        expected_result = {
            'status': 'pass',
            'end': 1,
            'log_raw': '\nPassed resource sanity checks.',
            'exit_code': 0,
            'start': 0,
            'test_file': "resource_sanity_checks"
        }
        self.assertEqual(observed_result, expected_result)

    def test_post_run_check_ftdc(self):
        """
        Runs the full post run check with FTDC resource checks.
        """
        arg_string = \
            "--rev 0ff97139df609ae1847da9bfb25c35d209e0936e -f {0}core_workloads_wt.history.json "\
            "-t {0}linux-standalone.core_workloads_WT.tags.json --refTag 3.2.1-Baseline " \
            "--overrideFile {0}system_perf_override.json " \
            "--log-analysis {0}core_workloads_reports " \
            "--project_id sys-perf --task_name core_workloads_WT --variant linux-standalone " \
            "--report-file {0}report_ftdc.json --out-file /dev/null".format(
                test_utils.FIXTURE_DIR_PATH)
        post_run_check.main(arg_string.split(" "))
        self.assertTrue(
            test_utils.eq_fixture_json_files("report_ftdc.json",
                                             "post_run_check_ftdc.report.json.ok"))
        os.remove("{0}report_ftdc.json".format(test_utils.FIXTURE_DIR_PATH))

    def test_post_run_check(self):
        """
        Runs the full post run check without FTDC resource checks.
        """
        arg_string = \
            "--rev 0ff97139df609ae1847da9bfb25c35d209e0936e -f {0}core_workloads_wt.history.json "\
            "-t {0}linux-standalone.core_workloads_WT.tags.json --refTag 3.2.1-Baseline " \
            "--overrideFile {0}system_perf_override.json " \
            "--project_id sys-perf --task_name core_workloads_WT --variant linux-standalone " \
            "--report-file {0}report.json --out-file /dev/null".format(test_utils.FIXTURE_DIR_PATH)
        post_run_check.main(arg_string.split(" "))
        self.assertTrue(
            test_utils.eq_fixture_json_files("report.json", "post_run_check.report.json.ok"))
        os.remove("{0}report.json".format(test_utils.FIXTURE_DIR_PATH))

if __name__ == '__main__':
    unittest.main()
