"""Tests for bin/common/workload_output_parser.py"""
import json
import logging
import os
import sys
import unittest

# TODO: Learn how to do this correctly without complaint from pylint
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/common")
#pylint: disable=wrong-import-position,wrong-import-order
from workload_output_parser import parse_test_results, validate_config

LOG = logging.getLogger(__name__)


class WorkloadOutputParserTestCase(unittest.TestCase):
    """Unit tests for workload_output_parser.py."""

    def setUp(self):
        """Set some common input data"""
        self.tests = [
            {'id': 'benchRun-unittest',
             'type': 'shell'},
            {'id': 'ycsb-unittest',
             'type': 'ycsb'},
            {'id': 'fio-unittest',
             'type': 'fio'},
            {'id': 'iperf-unittest',
             'type': 'iperf'}
        ] # yapf: disable
        self.config = {
            'test_control': {
                'task_name': 'parser_unittest',
                'reports_dir_basename': 'bin/tests/artifacts',
                'perf_json': {
                    'path': 'bin/tests/artifacts/perf.unittest-out.json'
                },
                'output_file' : {
                    'mongoshell': 'test_screen_capture.log-mongoshell',
                    'ycsb': 'test_screen_capture.log-ycsb',
                    'fio': 'fio.json',
                    'iperf': 'iperf.json'
                },
                'run': [
                    {'id': 'mock-test-foo',
                     'type': 'mongoshell'},
                    {'id': 'mock-test-bar',
                     'type': 'ycsb'},
                    {'id': 'mock-test-fio',
                     'type': 'fio'},
                    {'id': 'mock-test-iperf',
                     'type': 'iperf'}
                ]
            }
        } # yapf: disable
        self.timer = {'start': 1, 'end': 2}

        self.perf_json_path = self.config['test_control']['perf_json']['path']
        # Need to ensure clean start state
        if os.path.exists(self.perf_json_path):
            os.remove(self.perf_json_path)

    def tearDown(self):
        """Cleanup"""
        if os.path.exists(self.perf_json_path):
            os.remove(self.perf_json_path)

    def test_generate_perf_json(self):
        """Generates a perf.new.json file from a "test results" that combines all 4 test types."""
        for test in self.tests:
            LOG.debug("Parsing results for test %s", test['id'])
            parse_test_results(test, self.config, self.timer)
        # Verify output file
        with open(self.perf_json_path) as file_handle:
            result_perf_json = json.load(file_handle)
        with open("{}.ok".format(self.perf_json_path)) as file_handle:
            expected_perf_json = json.load(file_handle)
        self.assertEqual(result_perf_json, expected_perf_json)

    def test_validate_config(self):
        """Test workload_output_parser.validate_config()"""
        validate_config(self.config)

        with self.assertRaises(NotImplementedError):
            self.config['test_control']['run'][0]['type'] = "no_such_test_type"
            validate_config(self.config)
