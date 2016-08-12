"""Unit tests for `ftdc_analysis.py`."""

import unittest

import ftdc_analysis
from tests import test_utils

class TestFtdcAnalysis(unittest.TestCase):
    """Test suite."""

    def test_resource_rules_pass(self):
        """ Specifically test that we get the expected report info for resource sanity checks
        """
        dir_path = '{0}core_workloads_reports'.format(test_utils.FIXTURE_DIR_PATH)
        project = 'sys-perf'
        variant = 'linux-standalone'
        constant_values = {'max_thread_level': 64}
        observed_result = ftdc_analysis.resource_rules(dir_path, project, variant, constant_values)
        expected_result = {
            'status': 'pass',
            'end': 1,
            'log_raw': '\nPassed resource sanity checks.',
            'exit_code': 0,
            'start': 0,
            'test_file': "resource_sanity_checks"
        }
        self.assertEqual(observed_result, expected_result)

