"""
Unit tests for `post_run_check.py`.
"""

import os
import unittest

import post_run_check
from tests import test_utils


class TestPostRunCheck(unittest.TestCase):
    """Test suite."""

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


if __name__ == '__main__':
    unittest.main()
