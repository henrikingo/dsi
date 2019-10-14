"""
Unit tests for `compare.py`.
"""

import os

import unittest

from test_lib.fixture_files import FixtureFiles
import compare

FIXTURE_FILES = FixtureFiles(os.path.dirname(__file__))


class TestCompare(unittest.TestCase):
    """
    Test suite.
    """
    def runTest(self):
        """
        Load comparison data from two different sets of comparison/baseline JSON files and compare
        the output of `compare()` against the expected results (stored in another JSON file).
        """
        for test_name in ["core_workloads_wt", "industry_benchmarks_wt"]:
            baseline_run = FIXTURE_FILES.load_json_file(
                "test_compare/{}.baseline.json".format(test_name))
            comparison_run = FIXTURE_FILES.load_json_file(
                "test_compare/{}.comparison.json".format(test_name))
            exp_output = FIXTURE_FILES.load_json_file(
                "test_compare/{}.output.json".format(test_name))

            actual_output = compare.compare(comparison_run, baseline_run)

            self.assertEqual(actual_output, exp_output,
                             'Comparison failed for "{}".'.format(test_name))
