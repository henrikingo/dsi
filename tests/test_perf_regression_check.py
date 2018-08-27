"""
Unit tests for `perf_regression_check.py`.
"""

import os
import unittest

from test_lib.fixture_files import FixtureFiles
import perf_regression_check

FIXTURE_FILES = FixtureFiles(os.path.dirname(__file__))


class TestPerfRegressionCheck(unittest.TestCase):
    """Test suite."""

    def runTest(self):
        """
        Run the script and compare the file it generates to an expected one.
        """
        regenerate_output_files = False  #Note: True causes all tests to pass

        report_file = "report.json"
        ok_file = "perf_regression.report.json.ok"
        arg_string = \
            "-f {0}/delayed_trigger_queries.history.json " \
            "--rev 0ff97139df609ae1847da9bfb25c35d209e0936e " \
            "-t {0}/linux-wt-standalone.query.tags.json --refTag 3.2.1-Baseline " \
            "--overrideFile {0}/perf_override.json --variant linux-wt-standalone " \
            "--threshold 0.10 --threadThreshold 0.15 --out-file /dev/null " \
            "--report-file {0}/{1}"

        args = arg_string.format(FIXTURE_FILES.fixture_dir_path, report_file).split(" ")
        perf_regression_check.main(args)

        if regenerate_output_files:
            args = arg_string.format(FIXTURE_FILES.fixture_dir_path, ok_file).split(" ")
            perf_regression_check.main(args)

        self.assertTrue(FIXTURE_FILES.json_files_equal(report_file, ok_file))
        os.remove(FIXTURE_FILES.fixture_file_path(report_file))
