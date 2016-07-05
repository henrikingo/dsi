"""
Unit tests for `dashboard_gen.py`.
"""

import unittest

import dashboard_gen
from tests import test_utils

class TestDashboardGen(unittest.TestCase):
    """Test suite."""

    def runTest(self):
        """
        Run the script and compare the file it generates to an expected one.
        """

        arg_string = \
            "--rev 0ff97139df609ae1847da9bfb25c35d209e0936e -f {0}core_workloads_wt.history.json "\
            "-t {0}linux-standalone.core_workloads_WT.tags.json --refTag 3.2.1-Baseline " \
            "--overrideFile {0}system_perf_override.json --project_id sys-perf " \
            "--task_name core_workloads_WT --variant linux-standalone --jira-user fake-user " \
            "--jira-password fake-passwd --dashboard-file {0}dashboard.json".format(
                test_utils.FIXTURE_DIR_PATH)

        dashboard_gen.main(arg_string.split(" "))
        self.assertTrue(
            test_utils.eq_fixture_json_files("dashboard.json", "dashboard_gen.dashboard.json.ok"))

if __name__ == "__main__":
    unittest.main()
