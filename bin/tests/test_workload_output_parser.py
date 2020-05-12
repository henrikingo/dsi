"""Tests for bin/common/workload_output_parser.py"""

import logging
import os
import unittest

from test_control import validate_config

from common.workload_output_parser import parse_test_results
from test_lib.fixture_files import FixtureFiles

FIXTURE_FILES = FixtureFiles(os.path.dirname(__file__))
LOG = logging.getLogger(__name__)


class WorkloadOutputParserTestCase(unittest.TestCase):
    """Unit tests for workload_output_parser.py."""
    def setUp(self):
        """Set some common input data"""
        self.tests = [
            {'id': 'genny-unittest',
             'type': 'genny',
             'output_files': ['genny-metrics.json']},
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
            {'id': 'tpcc-unittest',
             'type': 'tpcc',
             'output_files': 'results.log'},
            {'id': 'sysbench-unittest',
             'type': 'sysbench'}
        ] # yapf: disable
        self.config = {
            'test_control': {
                'task_name': 'parser_unittest',
                'reports_dir_basename': FIXTURE_FILES.fixture_dir_path,
                'perf_json': {
                    'path': FIXTURE_FILES.fixture_file_path('perf.unittest-out.json')
                },
                'output_file': {
                    'mongoshell': 'test_output.log',
                    'ycsb': 'test_output.log',
                    'fio': 'fio.json',
                    'iperf': 'iperf.json',
                    'tpcc': 'results.log',
                    'sysbench': 'test_output.log'
                },
                'run': [
                    {'id': 'mock-genny-foo',
                     'type': 'genny'},
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
                    {'id': 'mock-test-tpcc-request',
                     'type': 'tpcc'},
                    {'id': 'mock-test-sysbench',
                     'type': 'sysbench'}
                ],
            },
            'mongodb_setup': {
                'mongod_config_file': {
                    'storage': {
                        'engine': 'wiredTiger'
                    }
                },
                'meta': {
                    'is_atlas': False
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
        """Generates a perf.json file from a "test results" that combines all 4 test types."""
        for test in self.tests:
            LOG.debug("Parsing results for test %s", test['id'])
            parse_test_results(test, self.config, self.timer)

        # Verify output file
        FIXTURE_FILES.assert_json_files_equal(self,
                                              expect="{}.ok".format(self.perf_json_path),
                                              actual=self.perf_json_path)

    def test_centos_fio_perf_json(self):
        """Generate a perf.json from a "test results" that uses the fio.json from fio on centos """
        LOG.debug("Parsing results for fio on centos")
        test = {'id': 'fio-unittest', 'type': 'fio'}
        self.config['test_control']['output_file']['fio'] = 'fio-centos.json'
        parse_test_results(test, self.config, self.timer)

        perf_json_path = FIXTURE_FILES.fixture_file_path('perf.unittest-out-fio-centos.json')
        FIXTURE_FILES.assert_json_files_equal(self,
                                              expect="{}.ok".format(perf_json_path),
                                              actual=self.perf_json_path)

    def test_atlas_perf_json(self):
        """Generates a perf.json file but omitting fio and iperf."""
        self.config['mongodb_setup']['meta']['is_atlas'] = True
        path = FIXTURE_FILES.fixture_file_path('perf.atlas.json')
        self.config['test_control']['perf_json']['path'] = path
        self.perf_json_path = path

        for test in self.tests:
            LOG.debug("Parsing results for test %s", test['id'])
            parse_test_results(test, self.config, self.timer)

        # Verify output file
        FIXTURE_FILES.assert_json_files_equal(self,
                                              expect="{}.ok".format(self.perf_json_path),
                                              actual=self.perf_json_path)

    def test_validate_config(self):
        """Test workload_output_parser.validate_config()"""
        validate_config(self.config)

        with self.assertRaises(NotImplementedError):
            self.config['test_control']['run'][0]['type'] = "no_such_test_type"
            validate_config(self.config)
