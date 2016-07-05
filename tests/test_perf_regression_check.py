"""
Unit tests for `perf_regression_check.py`.
"""

import unittest

import perf_regression_check
from tests import test_utils

class TestPerfRegressionCheck(unittest.TestCase):
    """Test suite."""

    def runTest(self):
        """
        Run the script and compare the file it generates to an expected one.
        """

        arg_string = \
            "-f {0}queries.history.json --rev 0ff97139df609ae1847da9bfb25c35d209e0936e " \
            "-t {0}linux-wt-standalone.query.tags.json --refTag 3.2.1-Baseline " \
            "--overrideFile {0}perf_override.json --variant linux-wt-standalone " \
            "--threshold 0.10 --threadThreshold 0.15 --out-file /dev/null " \
            "--report-file {0}report.json".format(test_utils.FIXTURE_DIR_PATH)
        perf_regression_check.main(arg_string.split(" "))
        self.assertTrue(
            test_utils.eq_fixture_json_files("report.json", "perf_regression.report.json.ok"))
