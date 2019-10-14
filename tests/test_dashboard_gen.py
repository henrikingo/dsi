"""
Unit tests for `dashboard_gen.py`.
"""

import os
import unittest

from test_lib.fixture_files import FixtureFiles
import dashboard_gen

FIXTURE_FILES = FixtureFiles(os.path.dirname(__file__))


class TestDashboardGen(unittest.TestCase):
    """
    Test suite.
    """
    def tearDown(self):
        """
        Remove the temperary test files
        """
        os.remove(FIXTURE_FILES.fixture_file_path("dashboard.json"))

    def test_sysperf(self):
        """
        Run the script and compare the file it generates to an expected one for sys-perf.
        """

        arg_string = \
            "--rev 0ff97139df609ae1847da9bfb25c35d209e0936e -f {0}/core_workloads_wt.history.json "\
            "-t {0}/linux-standalone.core_workloads_WT.tags.json --refTag 3.2.1-Baseline " \
            "--overrideFile {0}/system_perf_override.json --project_id sys-perf " \
            "--task_name core_workloads_WT --variant linux-standalone --jira-user fake-user " \
            "--jira-password fake-passwd --dashboard-file {0}/dashboard.json".format(
                FIXTURE_FILES.fixture_dir_path)

        dashboard_gen.main(arg_string.split(" "))
        self.assertTrue(
            FIXTURE_FILES.json_files_equal("dashboard.json", "dashboard_gen.dashboard.json.ok"))

    def test_mongo_perf(self):
        """
        Run the script and compare the file it generates to an expected one for mongo-perf.
        """
        arg_string = \
            "--rev 0ff97139df609ae1847da9bfb25c35d209e0936e -f {0}/queries.history.json "\
            "-t {0}/linux-wt-standalone.query.tags.json --refTag 3.2.1-Baseline " \
            "--overrideFile {0}/system_perf_override.json --project_id performance " \
            "--task_name core_workloads_WT --variant linux-standalone --jira-user fake-user " \
            "--jira-password fake-passwd --dashboard-file {0}/dashboard.json".format(
                FIXTURE_FILES.fixture_dir_path)

        dashboard_gen.main(arg_string.split(" "))
        self.assertTrue(
            FIXTURE_FILES.json_files_equal("dashboard.json",
                                           "dashboard_gen_perf.dashboard.json.ok"))


if __name__ == "__main__":
    unittest.main()
