"""
Unit tests for `compare.py`.
"""

import unittest
import compare
from tests import test_utils


class TestCompare(unittest.TestCase):
    """Test suite."""

    def runTest(self):
        """
        Load comparison data from two different sets of comparison/baseline JSON files and compare
        the output of `compare()` against the expected results (stored in another JSON file).
        """

        for test_name in ["core_workloads_wt", "industry_benchmarks_wt"]:
            baseline_run = test_utils.read_fixture_json_file(
                "test_compare/{}.baseline.json".format(test_name))
            comparison_run = test_utils.read_fixture_json_file(
                "test_compare/{}.comparison.json".format(test_name))
            exp_output = test_utils.read_fixture_json_file(
                "test_compare/{}.output.json".format(test_name))

            actual_output = compare.compare(comparison_run, baseline_run)

            self.assertEqual(actual_output, exp_output,
                             'Comparison failed for "{}".'.format(test_name))
