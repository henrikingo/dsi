"""Unit tests for `ftdc_analysis.py`."""
# pylint: disable=protected-access

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

    def test__get_host_ip_info(self):
        """ add tests for the new reports directory layout """

        return_value = ftdc_analysis._get_host_ip_info('diag-p1-54.83.180.179')
        self.assertTrue(return_value is None)

        return_value = ftdc_analysis._get_host_ip_info('mongod.0')
        expected = 'mongod.0'
        self.assertEqual(return_value, expected)

if __name__ == '__main__':
    unittest.main()
