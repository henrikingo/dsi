"""
Unit tests for `perf_regression_check.py`.
"""

import os
import unittest

import perf_regression_check
from tests import test_utils

class TestPerfRegressionCheck(unittest.TestCase):
    """Test suite."""

    def runTest(self):
        """
        Run the script and compare the file it generates to an expected one.
        """
        regenerate_output_files = False #Note: causes all tests to pass

        report_file = "report.json"
        arg_string = \
            "-f {0}delayed_trigger_queries.history.json " \
            "--rev 0ff97139df609ae1847da9bfb25c35d209e0936e " \
            "-t {0}linux-wt-standalone.query.tags.json --refTag 3.2.1-Baseline " \
            "--overrideFile {0}perf_override.json --variant linux-wt-standalone " \
            "--threshold 0.10 --threadThreshold 0.15 --out-file /dev/null " \
            "--report-file {0}{1}".format(test_utils.FIXTURE_DIR_PATH, report_file)
        perf_regression_check.main(arg_string.split(" "))

        if regenerate_output_files:
            copy_arg_string = \
            "-f {0}delayed_trigger_queries.history.json " \
            "--rev 0ff97139df609ae1847da9bfb25c35d209e0936e " \
            "-t {0}linux-wt-standalone.query.tags.json --refTag 3.2.1-Baseline " \
            "--overrideFile {0}perf_override.json --variant linux-wt-standalone " \
            "--threshold 0.10 --threadThreshold 0.15 --out-file /dev/null " \
            "--report-file {0}{1}".format(test_utils.FIXTURE_DIR_PATH,
                                          "perf_regression.report.json.ok")
            perf_regression_check.main(copy_arg_string.split(" "))

        self.assertTrue(
            test_utils.eq_fixture_json_files(report_file, "perf_regression.report.json.ok"))
        os.remove(test_utils.fixture_file_path(report_file))
