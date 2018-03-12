"""Tests for bin/common/workload_output_parser.py"""
import json
import logging
import os
import sys
import unittest
import json_diff

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/common")
from workload_output_parser import parse_test_results, validate_config

LOG = logging.getLogger(__name__)


class WorkloadOutputParserTestCase(unittest.TestCase):
    """Unit tests for workload_output_parser.py."""

    def assert_json_files_equal(self, expect, actual):
        """
        Pretty-print a json diff report if contents if
        expect != actual

        :param IO expect: expected json file IO
        :param IO actual: acttual json file IO
        """
        # While not strictly necessary, giving a nice diff view
        # of the json differences helps immensely in debugging these tests
        # versus just being able to see
        #     {...some-huge-string...} != {...some-other-huge-string....}
        diff = json_diff.Comparator(open(expect), open(actual))
        diff_res = diff.compare_dicts()
        outs = unicode(json_diff.HTMLFormatter(diff_res))

        with open(actual) as file_handle:
            result_perf_json = json.load(file_handle)
        with open(expect) as file_handle:
            expected_perf_json = json.load(file_handle)

        # pylint: disable=invalid-name
        self.maxDiff = None
        self.assertEqual(result_perf_json, expected_perf_json, outs)

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
             'type': 'iperf'},
            {'id': 'linkbench-load-unittest',
             'type': 'linkbench',
             'output_files': ['load-phase-stats.csv']},
            {'id': 'linkbench-request-unittest',
             'type': 'linkbench',
             'output_files': ['request-phase-stats.csv']},
        ] # yapf: disable
        self.config = {
            'test_control': {
                'task_name': 'parser_unittest',
                'reports_dir_basename': 'bin/tests/artifacts',
                'perf_json': {
                    'path': 'bin/tests/artifacts/perf.unittest-out.json'
                },
                'output_file': {
                    'mongoshell': 'test_output.log',
                    'ycsb': 'test_output.log',
                    'fio': 'fio.json',
                    'iperf': 'iperf.json',
                },
                'run': [
                    {'id': 'mock-test-foo',
                     'type': 'mongoshell'},
                    {'id': 'mock-test-bar',
                     'type': 'ycsb'},
                    {'id': 'mock-test-fio',
                     'type': 'fio'},
                    {'id': 'mock-test-iperf',
                     'type': 'iperf'},
                    {'id': 'mock-test-linkbench-load',
                     'type': 'linkbench'},
                    {'id': 'mock-test-linkbench-request',
                     'type': 'linkbench'},
                ]
            },
            'mongodb_setup': {
                'mongod_config_file': {
                    'storage': {
                        'engine': 'wiredTiger'
                    }
                }
            }
        } # yapf: disable
        self.timer = {'start': 1.001, 'end': 2.002}

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
        self.assert_json_files_equal(
            expect="{}.ok".format(self.perf_json_path), actual=self.perf_json_path)

    def test_validate_config(self):
        """Test workload_output_parser.validate_config()"""
        validate_config(self.config)

        with self.assertRaises(NotImplementedError):
            self.config['test_control']['run'][0]['type'] = "no_such_test_type"
            validate_config(self.config)
