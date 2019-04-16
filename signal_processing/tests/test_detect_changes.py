"""
Unit tests for signal_processing/detect_changes.py.
"""

import os
import time
import unittest

from click.testing import CliRunner
from mock import ANY, MagicMock, call, patch

import signal_processing.detect_changes as detect_changes
from signal_processing.change_points.detection import ChangePointsDetection
from signal_processing.change_points.weights import DEFAULT_WEIGHTING
from signal_processing.commands import jobs
from signal_processing.detect_changes import main
from signal_processing.model.points import PointsModel
from test_lib.fixture_files import FixtureFiles
import test_lib.structlog_for_test as structlog_for_test

FIXTURE_FILES = FixtureFiles(os.path.dirname(__file__))


def statistics(i):
    """ helper function to create dummy stats:

    :parameter int i: An int, generally the index.
    :return: A stats dict().
    """
    return {'next': i * 10, 'previous': (i * 10) + 1}


NS = 'signal_processing.detect_changes'
POINT_NS = 'signal_processing.model.points'


def ns(relative_name):  # pylint: disable=invalid-name
    """Return a full name from a name relative to the tested module's name space."""
    return NS + '.' + relative_name


def point_ns(relative_name):  # pylint: disable=invalid-name
    """Return a full name from a name relative to the tested module's name space."""
    return POINT_NS + '.' + relative_name


class TestTig1423(unittest.TestCase):
    """
    Test TIG-1423.
    """

    def setUp(self):
        file_parts = [
            'sys-perf', 'linux-1-node-replSet', 'bestbuy_query', 'canary_client-cpuloop-10x', '1'
        ] + ['{}.json'.format('standard')]

        filename = os.path.join(*file_parts)
        self.fixture = FIXTURE_FILES.load_json_file(filename)
        self.expected = self.fixture['expected']
        self.data = self.fixture['data']

        self.mongo_uri = 'mongodb+srv://fake@dummy-server.mongodb.net/perf'
        self.sysperf_perf_json = FIXTURE_FILES.load_json_file('sysperf_perf.json')
        structlog_for_test.setup_logging()

    # pylint: disable=too-many-locals
    def test_detect_changes(self):
        """ test detect changes with real data.

        This is more of a system test, the data base and github access are stubbed.
        """
        # with patch('signal_processing.model.points.pymongo.MongoClient', autospec=True),\
        with patch(point_ns('pymongo.MongoClient'), autospec=True),\
             patch(ns('helpers.generate_thread_levels'), autospec=True) as mock_generate_thread_levels, \
             patch.object(PointsModel, 'get_closest_order', autospec=True) as mock_get_closest_order, \
             patch.object(PointsModel, 'get_points', autospec=True) as mock_get_points, \
             patch.object(ChangePointsDetection, '_get_git_hashes', autospec=True) as mock_get_git_hashes, \
             patch(point_ns('pymongo.DeleteMany')) as mock_delete, \
             patch(point_ns('pymongo.InsertOne')) as mock_insert:
            series = self.data['time_series']

            perf_json = {
                'project_id': series['project'],
                'variant': series['variant'],
                'task_name': series['task'],
                'data': {
                    'results': [{
                        'name': series['test']
                    }]
                },
                'thread_level': series['thread_level'],
            }
            mock_generate_thread_levels.return_value = [{
                'project': series['project'],
                'variant': series['variant'],
                'task': series['task'],
                'test': series['test'],
                'thread_level': series['thread_level'],
            }]

            change_points = self.data['change_points']

            mock_get_closest_order.return_value = self.data['start_order']
            mock_get_points.return_value = self.data['time_series']
            mock_get_git_hashes.side_effect = self.data['all_suspect_revisions']
            test_driver = detect_changes.DetectChangesDriver(
                perf_json, self.mongo_uri, DEFAULT_WEIGHTING, 0.001, 'mongo_repo', pool_size=0)

            test_driver.run()
            query = {
                'project': u'sys-perf',
                'variant': u'linux-1-node-replSet',
                'task': u'bestbuy_query',
                'test': u'canary_client-cpuloop-10x',
                'thread_level': u'1',
                'order': {
                    '$gt': 13527
                }
            }

            mock_delete.assert_called_once_with(query)
            mock_insert.assert_has_calls([call(ANY) for _ in range(2)])
            # spot check the important values
            for i, calls in enumerate(mock_insert.call_args_list):
                args, _ = calls
                self.assertEqual(change_points[i]['order'], args[0]['order'])
                self.assertEqual(change_points[i]['order_of_change_point'],
                                 args[0]['order_of_change_point'])
                subset = {}
                for key, value in change_points[i]['algorithm'].items():
                    if isinstance(value, float):
                        self.assertAlmostEqual(change_points[i]['algorithm'][key],
                                               args[0]['algorithm'][key])
                    else:
                        subset[key] = value
                self.assertDictContainsSubset(subset, args[0]['algorithm'])


# pylint: disable=invalid-name
class TestDetectChangesDriver(unittest.TestCase):
    """
    Test suite for the DetectChangesDriver class.
    """

    def setUp(self):
        self.mongo_uri = 'mongodb+srv://fake@dummy-server.mongodb.net/perf'
        self.sysperf_perf_json = FIXTURE_FILES.load_json_file('sysperf_perf.json')
        self.sysperf_points = FIXTURE_FILES.load_json_file('sysperf_points.json')

    @patch('multiprocessing.cpu_count', autospec=True)
    def test_constructor(self, mock_cpu_count):
        mock_cpu_count.return_value = 101
        test_driver = detect_changes.DetectChangesDriver(self.sysperf_perf_json, self.mongo_uri,
                                                         None, 0.001, 'mongo_repo')
        self.assertEquals(test_driver.pool_size, 200)

    @patch('multiprocessing.cpu_count', autospec=True)
    def test_constructor_pool_size(self, mock_cpu_count):
        test_driver = detect_changes.DetectChangesDriver(
            self.sysperf_perf_json, self.mongo_uri, None, 0.001, 'mongo_repo', pool_size=99)
        self.assertEquals(test_driver.pool_size, 99)

    def _test_run(self, min_points=None):
        """ test run. """

        with patch('multiprocessing.cpu_count', autospec=True) as mock_cpu_count, \
             patch('signal_processing.commands.jobs.Job', autospec=True) as mock_job_cls,\
             patch('signal_processing.commands.jobs.process_jobs', autospec=True) as mock_process_jobs,\
             patch(ns('PointsModel'), autospec=True) as mock_PointsModel:

            mock_job = MagicMock(name='mock_job')
            mock_job_cls.return_value = mock_job

            mock_process_jobs.return_value = ()
            mock_cpu_count.return_value = 101
            mock_model = mock_PointsModel.return_value

            test_identifiers = [{
                'project': self.sysperf_perf_json['project_id'],
                'variant': self.sysperf_perf_json['variant'],
                'task': self.sysperf_perf_json['task_name'],
                'test': test,
                'thread_level': '1'
            } for test in (u'mixed_insert', u'mixed_insert_bad', u'mixed_findOne')]

            mock_model.db.points.aggregate.return_value = test_identifiers
            mock_model.compute_change_points.return_value = (1, 2, 3)
            test_driver = detect_changes.DetectChangesDriver(
                self.sysperf_perf_json, self.mongo_uri, 0.001, 'mongo_repo', min_points=min_points)
            test_driver.run()
            mock_PointsModel.assert_called_once_with(
                self.mongo_uri, min_points, mongo_repo='mongo_repo', credentials=None)

            calls = [
                call(
                    mock_model.compute_change_points,
                    arguments=(test_identifier, 0.001),
                    identifier=test_identifier) for test_identifier in test_identifiers
            ]
            mock_job_cls.assert_has_calls(calls)

    def test_run_no_min_points(self):
        """ test run no min_points. """
        self._test_run()

    def test_run_with_min_points(self):
        """ test run with min_points. """
        self._test_run(min_points=750)


class TestMain(unittest.TestCase):
    """
    Test suite for the main function.
    """

    def setUp(self):
        self.runner = CliRunner()

    @patch(ns('detect_changes'))
    @patch(ns('config.ConfigDict'), autospec=True)
    @patch(ns('log.setup_logging'), autospec=True)
    def test_help(self, mock_logging, mock_config_dict, mock_detect_changes):
        """
        Test main responds to help.
        """
        result = self.runner.invoke(main, ['help'])
        self.assertEqual(result.exit_code, 2)

        mock_config_dict.assert_not_called()
        mock_detect_changes.assert_not_called()

    @patch(ns('detect_changes'))
    @patch(ns('config.ConfigDict'), autospec=True)
    @patch(ns('log.setup_logging'))
    def test_defaults(self, mock_logging, mock_config_dict, mock_detect_changes):
        """
        Test default params.
        """
        mock_detect_changes.return_value = None
        mock_config = mock_config_dict.return_value

        result = self.runner.invoke(main)
        self.assertEqual(result.exit_code, 0)

        mock_config_dict.assert_called_once()
        mock_config.load.assert_called_once()
        mock_logging.assert_called_once()
        mock_detect_changes.assert_called_once()

    @patch(ns('detect_changes'))
    @patch(ns('config.ConfigDict'), autospec=True)
    @patch(ns('log.setup_logging'))
    def test_params(self, mock_logging, mock_config_dict, mock_detect_changes):
        """
        Test main with params.
        """
        mock_detect_changes.return_value = None
        mock_config = mock_config_dict.return_value
        config = {
            'runtime': {
                'task_id': 'tid',
                'is_patch': 'patch'
            },
            'analysis': {
                'mongo_uri': 'muri'
            }
        }
        mock_config.__getitem__.side_effect = config.__getitem__

        result = self.runner.invoke(main, [
            '-l', 'logfile', '--pool-size', '1', '--minimum', '700', '-v', '--mongo-repo', 'repo',
            '--progressbar'
        ])
        self.assertEqual(result.exit_code, 0)

        mock_config_dict.assert_called_once()
        mock_config.load.assert_called_once()
        mock_logging.assert_called_once_with(True, filename='logfile')
        mock_detect_changes.assert_called_once_with(
            ANY, ANY, 'muri', 700, 1, mongo_repo='repo', progressbar=True)

    @patch(ns('detect_changes'))
    @patch(ns('config.ConfigDict'), autospec=True)
    @patch(ns('log.setup_logging'))
    def test_config_load(self, mock_logging, mock_config_dict, mock_detect_changes):
        """
        Test main config dict params.
        """
        mock_detect_changes.return_value = None
        mock_config = mock_config_dict.return_value
        config = {
            'runtime': {
                'task_id': 'tid',
                'is_patch': 'patch'
            },
            'analysis': {
                'mongo_uri': 'muri'
            }
        }
        mock_config.__getitem__.side_effect = config.__getitem__

        result = self.runner.invoke(main)
        self.assertEqual(result.exit_code, 0)

        mock_config_dict.assert_called_once()
        mock_config.load.assert_called_once()
        mock_logging.assert_called_once_with(False, filename='detect_changes.log')
        mock_detect_changes.assert_called_once_with(
            'tid', 'patch', 'muri', 500, None, mongo_repo='../src', progressbar=False)

    @patch(ns('detect_changes'))
    @patch(ns('config.ConfigDict'), autospec=True)
    @patch(ns('log.setup_logging'))
    def test_exception(self, mock_logging, mock_config_dict, mock_detect_changes):
        """
        Test main handles errors.

        """
        mock_detect_changes.return_value = (jobs.Job(time.sleep), )
        result = self.runner.invoke(main)
        self.assertEqual(result.exit_code, 2)
        self.assertIn('1 Unexpected Exceptions', result.output)
