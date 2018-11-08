"""
Unit tests for signal_processing/detect_changes.py.
"""

import os
import time
import unittest
from collections import OrderedDict, defaultdict
from mock import ANY, MagicMock, call, patch

import signal_processing.detect_changes as detect_changes
from signal_processing.commands import jobs
from signal_processing.detect_changes import main
from test_lib.fixture_files import FixtureFiles
from click.testing import CliRunner

FIXTURE_FILES = FixtureFiles(os.path.dirname(__file__))


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
                                                         0.001, 'mongo_repo')
        self.assertEquals(test_driver.pool_size, 100)

    @patch('multiprocessing.cpu_count', autospec=True)
    def test_constructor_pool_size(self, mock_cpu_count):
        test_driver = detect_changes.DetectChangesDriver(
            self.sysperf_perf_json, self.mongo_uri, 0.001, 'mongo_repo', pool_size=99)
        self.assertEquals(test_driver.pool_size, 99)

    @patch('multiprocessing.cpu_count', autospec=True)
    @patch('signal_processing.commands.jobs.Job', autospec=True)
    @patch('signal_processing.commands.jobs.process_jobs', autospec=True)
    @patch('signal_processing.detect_changes.PointsModel', autospec=True)
    def test_run(self, mock_PointsModel, mock_process_jobs, mock_job_cls, mock_cpu_count):
        mock_job = MagicMock(name='mock_job')
        mock_job_cls.return_value = mock_job

        mock_process_jobs.return_value = ()
        mock_cpu_count.return_value = 101
        mock_model = mock_PointsModel.return_value
        mock_model.compute_change_points.return_value = (1, 2, 3)
        test_driver = detect_changes.DetectChangesDriver(self.sysperf_perf_json, self.mongo_uri,
                                                         0.001, 'mongo_repo')
        test_driver.run()
        mock_PointsModel.assert_called_once_with(
            self.sysperf_perf_json, self.mongo_uri, mongo_repo='mongo_repo', credentials=None)

        calls = [
            call(
                mock_model.compute_change_points,
                arguments=(test, 0.001),
                identifier={
                    'project': self.sysperf_perf_json['project_id'],
                    'variant': self.sysperf_perf_json['variant'],
                    'task': self.sysperf_perf_json['task_name'],
                    'test': test
                }) for test in [u'mixed_insert', u'mixed_insert_bad', u'mixed_findOne']
        ]
        mock_job_cls.assert_has_calls(calls)


def copy_and_update(x, **kwargs):
    z = x.copy()
    z.update(kwargs)
    return z


class TestPointsModel(unittest.TestCase):
    """
    Test suite for the PointsModel class.
    """

    def setUp(self):
        self.mongo_uri = 'mongodb+srv://fake@dummy-server.mongodb.net/perf'
        self.sysperf_perf_json = FIXTURE_FILES.load_json_file('sysperf_perf.json')
        self.sysperf_points = FIXTURE_FILES.load_json_file('sysperf_points.json')

    def load_expected_points(self):
        expected_series = defaultdict(list)
        expected_revisions = defaultdict(list)
        expected_orders = defaultdict(list)
        expected_create_times = defaultdict(list)
        expected_task_ids = defaultdict(list)

        expected_points = {
            'series': expected_series,
            'revisions': expected_revisions,
            'orders': expected_orders,
            'create_times': expected_create_times,
            'task_ids': expected_task_ids
        }

        expected_num_points = 0
        for point in self.sysperf_points:
            for result in point['results']:
                expected_series[result['thread_level']].append(result['ops_per_sec'])
                expected_revisions[result['thread_level']].append(point['revision'])
                expected_orders[result['thread_level']].append(point['order'])
                expected_create_times[result['thread_level']].append(point['create_time'])
                expected_task_ids[result['thread_level']].append(point['task_id'])
                expected_num_points += 1
        return expected_num_points, expected_points

    @patch('signal_processing.detect_changes.pymongo.MongoClient', autospec=True)
    def test_get_points(self, mock_mongo_client):
        expected_query = OrderedDict(
            [('project', self.sysperf_perf_json['project_id']),
             ('variant', self.sysperf_perf_json['variant']), ('task',
                                                              self.sysperf_perf_json['task_name']),
             ('test', self.sysperf_perf_json['data']['results'][0]['name'])])
        expected_projection = {
            'results': 1,
            'revision': 1,
            'order': 1,
            'create_time': 1,
            'task_id': 1,
            '_id': 0
        }
        expected_num_points, expected_points = self.load_expected_points()

        mock_db = MagicMock(name='db', autospec=True)
        mock_cursor = MagicMock(name='cursor', autospec=True)
        mock_mongo_client.return_value.get_database.return_value = mock_db
        mock_db.points.find.return_value.sort = mock_cursor
        mock_cursor.return_value = self.sysperf_points
        test_model = detect_changes.PointsModel(self.sysperf_perf_json, self.mongo_uri)

        actual_num_points, actual_query, actual_points = test_model.get_points(
            self.sysperf_perf_json['data']['results'][0]['name'])

        self.assertEqual(actual_num_points, expected_num_points)
        self.assertEqual(actual_query, expected_query)
        self.assertEqual(actual_points, expected_points)

        mock_mongo_client.assert_called_once_with(self.mongo_uri)
        mock_mongo_client.return_value.get_database.assert_called_once_with()
        mock_db.points.find.assert_called_once_with(expected_query, expected_projection)
        mock_db.points.find.return_value.sort.assert_called_once_with([('order', 1)])

    @patch('signal_processing.detect_changes.pymongo.MongoClient', autospec=True)
    def test_get_points_custom_limit(self, mock_mongo_client):
        """
        Test that limit is called on cursor when specified.
        """
        limit = 10
        mock_db = MagicMock(name='db', autospec=True)
        mock_cursor = MagicMock(name='cursor', autospec=True)
        mock_mongo_client.return_value.get_database.return_value = mock_db
        mock_db.points.find.return_value.sort = mock_cursor
        test_model = detect_changes.PointsModel(self.sysperf_perf_json, self.mongo_uri, limit=limit)
        test_model.get_points(self.sysperf_perf_json['data']['results'][0]['name'])
        mock_cursor.return_value.limit.assert_called_with(limit)

    @patch('pymongo.InsertOne')
    @patch('pymongo.DeleteMany')
    @patch('signal_processing.qhat.get_githashes_in_range_repo')
    @patch('signal_processing.qhat.QHat', autospec=True)
    @patch('signal_processing.detect_changes.PointsModel.get_points', autospec=True)
    @patch('signal_processing.detect_changes.pymongo.MongoClient', autospec=True)
    def test_compute_change_points(self, mock_mongo_client, mock_get_points, mock_qhat_class,
                                   mock_git, mock_delete, mock_insert):
        # pylint: disable=too-many-locals
        mock_delete.return_value = "DeleteMany"
        mock_insert.side_effect = ["InsertOne 1", "InsertOne 2"]
        expected_query = OrderedDict(
            [('project', self.sysperf_perf_json['project_id']),
             ('variant', self.sysperf_perf_json['variant']),
             ('task', self.sysperf_perf_json['task_name']),
             ('test', self.sysperf_perf_json['data']['results'][0]['name'])])  # yapf: disable
        expected_inserts = [
            OrderedDict([
                ('project', self.sysperf_perf_json['project_id']),
                ('variant', self.sysperf_perf_json['variant']),
                ('task', self.sysperf_perf_json['task_name']),
                ('test', self.sysperf_perf_json['data']['results'][0]['name']),
                ('order', i),
                ('task_id', 'task {}'.format(i))]) for i in range(1, 3)]   # yapf: disable
        mock_db = MagicMock(name='db', autospec=True)
        mock_bulk = MagicMock(name='bulk', autospec=True)
        mock_mongo_client.return_value.get_database.return_value = mock_db
        mock_db.change_points.find.return_value = []
        mock_db.change_points.bulk_write.return_value = mock_bulk

        expected_data = {
            'series': {
                4: [1, 2]
            },
            'revisions': {
                4: ['revision 1', 'revision 2']
            },
            'orders': {
                4: [1, 2]
            },
            'create_times': {
                4: [1, 2]
            },
            'task_ids': {
                4: ['task 1', 'task 2']
            }
        }

        mock_get_points.return_value = ['many_points', expected_query, expected_data]
        mock_qhat = MagicMock(
            name='qhat', autospec=True, change_points=[{
                'order': 1
            }, {
                'order': 2
            }])
        mock_qhat_class.return_value = mock_qhat

        test = self.sysperf_perf_json['data']['results'][0]['name']
        test_model = detect_changes.PointsModel(self.sysperf_perf_json, self.mongo_uri)
        actual = test_model.compute_change_points(test, weighting=0.001)
        thread_level = 4
        expected_params = {
            k: v[thread_level]
            for k, v in expected_data.iteritems() if k != 'task_ids'
        }
        expected_params['thread_level'] = thread_level
        expected_params['testname'] = test
        mock_qhat_class.assert_called_once_with(
            expected_params, pvalue=None, credentials=None, mongo_repo=None, weighting=0.001)

        mock_delete.assert_called_once_with(expected_query)
        mock_insert.assert_has_calls(
            [call(expected_insert) for expected_insert in expected_inserts])
        mock_db.change_points.bulk_write.assert_called_once_with(
            ["DeleteMany", "InsertOne 1", "InsertOne 2"])
        self.assertEqual(actual, ('many_points', 2))
        mock_mongo_client.assert_called_once_with(self.mongo_uri)
        mock_mongo_client.return_value.get_database.assert_called_once_with()
        mock_db.change_points.find.assert_called_once_with(expected_query)

    @patch('pymongo.InsertOne')
    @patch('pymongo.DeleteMany')
    @patch('signal_processing.qhat.get_githashes_in_range_repo')
    @patch('signal_processing.qhat.QHat', autospec=True)
    @patch('signal_processing.detect_changes.PointsModel.get_points', autospec=True)
    @patch('signal_processing.detect_changes.pymongo.MongoClient', autospec=True)
    def test_compute_change_points_rollback(self, mock_mongo_client, mock_get_points,
                                            mock_qhat_class, mock_git, mock_delete, mock_insert):
        # pylint: disable=too-many-locals
        mock_delete.side_effect = [Exception('boom'), "DeleteMany"]
        mock_insert.side_effect = ["InsertOne 1", "InsertOne 2"]
        expected_query = OrderedDict(
            [('project', self.sysperf_perf_json['project_id']),
             ('variant', self.sysperf_perf_json['variant']),
             ('task', self.sysperf_perf_json['task_name']),
             ('test', self.sysperf_perf_json['data']['results'][0]['name'])])  # yapf: disable

        mock_db = MagicMock(name='db', autospec=True)
        mock_bulk = MagicMock(name='bulk', autospec=True)
        mock_mongo_client.return_value.get_database.return_value = mock_db

        before = [1, 2]
        mock_db.change_points.find.return_value = before
        mock_db.change_points.bulk_write.return_value = mock_bulk

        expected_data = {
            'series': {
                4: [1, 2]
            },
            'revisions': {
                4: ['revision 1', 'revision 2']
            },
            'orders': {
                4: [1, 2]
            },
            'create_times': {
                4: [1, 2]
            },
            'task_ids': {
                4: ['task 1', 'task 2']
            }
        }

        mock_get_points.return_value = ['many_points', expected_query, expected_data]
        mock_qhat = MagicMock(
            name='qhat', autospec=True, change_points=[{
                'order': 1
            }, {
                'order': 2
            }])
        mock_qhat_class.return_value = mock_qhat

        test = self.sysperf_perf_json['data']['results'][0]['name']
        test_model = detect_changes.PointsModel(self.sysperf_perf_json, self.mongo_uri)
        with self.assertRaises(Exception) as context:
            test_model.compute_change_points(test, weighting=0.001)
        self.assertTrue('boom' in context.exception)

        thread_level = 4
        expected_params = {
            k: v[thread_level]
            for k, v in expected_data.iteritems() if k != 'task_ids'
        }
        expected_params['thread_level'] = thread_level
        expected_params['testname'] = test
        mock_qhat_class.assert_called_once_with(
            expected_params, pvalue=None, credentials=None, mongo_repo=None, weighting=0.001)

        # delete is called twice in this case
        mock_delete.assert_has_calls([call(expected_query), call(expected_query)])
        mock_insert.assert_has_calls([call(expected_insert) for expected_insert in before])
        mock_db.change_points.bulk_write.assert_called_once_with(
            ["DeleteMany", "InsertOne 1", "InsertOne 2"])
        mock_mongo_client.assert_called_once_with(self.mongo_uri)
        mock_mongo_client.return_value.get_database.assert_called_once_with()
        mock_insert.assert_has_calls([call(1), call(2)])

    @patch('pymongo.InsertOne')
    @patch('pymongo.DeleteMany')
    @patch('signal_processing.qhat.get_githashes_in_range_repo')
    @patch('signal_processing.qhat.QHat', autospec=True)
    @patch('signal_processing.detect_changes.PointsModel.get_points', autospec=True)
    @patch('signal_processing.detect_changes.pymongo.MongoClient', autospec=True)
    def test_compute_change_points_thread_level(self, mock_mongo_client, mock_get_points,
                                                mock_qhat_class, mock_git, mock_delete,
                                                mock_insert):
        """
        Test compute_change_points when a point has multiple thread levels.
        """
        mock_delete.return_value = "DeleteMany"
        mock_insert.side_effects = ["InsertOne 1"]

        expected_query = OrderedDict(
            [('project', self.sysperf_perf_json['project_id']),
             ('variant', self.sysperf_perf_json['variant']),
             ('task', self.sysperf_perf_json['task_name']),
             ('test', self.sysperf_perf_json['data']['results'][0]['name'])])  # yapf: disable
        mock_get_points.return_value = [
            'many_points', expected_query, {
                'series': OrderedDict([(4, [1, 2, 3]), (16, [3])]),
                'revisions': {
                    4: ['abc', 'bcd', 'cde'],
                    16: ['cde']
                },
                'orders': {
                    4: [0, 1, 2],
                    16: [2]
                },
                'create_times': {
                    4: [1, 2, 3],
                    16: [3]
                },
                'task_ids': {
                    4: ['task 1', 'task 2', 'task 3'],
                    16: ['task 3']
                }
            }
        ]
        test = self.sysperf_perf_json['data']['results'][0]['name']
        qhat_calls = [
            call(
                {
                    'series': [1, 2, 3],
                    'revisions': ['abc', 'bcd', 'cde'],
                    'orders': [0, 1, 2],
                    'create_times': [1, 2, 3],
                    'testname': test,
                    'thread_level': 4
                },
                pvalue=None,
                weighting=ANY,
                mongo_repo=ANY,
                credentials=ANY),
            call(
                {
                    'series': [3],
                    'revisions': ['cde'],
                    'orders': [2],
                    'create_times': [3],
                    'testname': test,
                    'thread_level': 16
                },
                pvalue=None,
                weighting=ANY,
                mongo_repo=ANY,
                credentials=ANY),
        ]

        mock_qhats = [
            MagicMock(name='qhat tl 4', autospec=True, change_points=[{
                'order': 0
            }]),
            MagicMock(name='qhat tl 16', autospec=True, change_points=[{
                'order': 2
            }])
        ]
        mock_qhat_class.side_effect = mock_qhats

        test_model = detect_changes.PointsModel(self.sysperf_perf_json, self.mongo_uri)
        test_model.compute_change_points(test, weighting=0.001)
        mock_qhat_class.assert_has_calls(qhat_calls)

    def _test_detect_changes(self, mock_evg_client, mock_etl_helpers, mock_driver, is_patch=False):
        """
        test_detect_changes helper.
        """
        mock_runner = mock_driver.return_value

        detect_changes.detect_changes('task_id', is_patch, 'mongo_uri', 1)
        mock_evg_client.assert_called_once()
        mock_driver.assert_called_once()
        mock_runner.run.assert_called_once()
        if is_patch:
            mock_etl_helpers.load.assert_not_called()
        else:
            mock_etl_helpers.load.assert_called_once()

    @patch('signal_processing.detect_changes.DetectChangesDriver', autospec=True)
    @patch('signal_processing.detect_changes.etl_helpers', autospec=True)
    @patch('signal_processing.detect_changes.evergreen_client.Client', autospec=True)
    def test_detect_changes_not_patch(self, mock_evg_client, mock_etl_helpers, mock_driver):
        """
        Test main and is not patch.
        """
        self._test_detect_changes(mock_evg_client, mock_etl_helpers, mock_driver)

    @patch('signal_processing.detect_changes.DetectChangesDriver', autospec=True)
    @patch('signal_processing.detect_changes.etl_helpers', autospec=True)
    @patch('signal_processing.detect_changes.evergreen_client.Client', autospec=True)
    def test_detect_changes_is_patch(self, mock_evg_client, mock_etl_helpers, mock_driver):
        """
        Test main and is patch.
        """
        self._test_detect_changes(mock_evg_client, mock_etl_helpers, mock_driver, is_patch=True)


class TestMain(unittest.TestCase):
    """
    Test suite for the main function.
    """

    def setUp(self):
        self.runner = CliRunner()

    @patch('signal_processing.detect_changes.detect_changes')
    @patch('signal_processing.detect_changes.config.ConfigDict', autospec=True)
    @patch('signal_processing.detect_changes.log.setup_logging', autospec=True)
    def test_help(self, mock_logging, mock_config_dict, mock_detect_changes):
        """
        Test main responds to help.
        """
        result = self.runner.invoke(main, ['help'])
        self.assertEqual(result.exit_code, 2)

        mock_config_dict.assert_not_called()
        mock_detect_changes.assert_not_called()

    @patch('signal_processing.detect_changes.detect_changes')
    @patch('signal_processing.detect_changes.config.ConfigDict', autospec=True)
    @patch('signal_processing.detect_changes.log.setup_logging')
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

    @patch('signal_processing.detect_changes.detect_changes')
    @patch('signal_processing.detect_changes.config.ConfigDict', autospec=True)
    @patch('signal_processing.detect_changes.log.setup_logging')
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

        result = self.runner.invoke(
            main,
            ['-l', 'logfile', '--pool-size', '1', '-v', '--mongo-repo', 'repo', '--progressbar'])
        self.assertEqual(result.exit_code, 0)

        mock_config_dict.assert_called_once()
        mock_config.load.assert_called_once()
        mock_logging.assert_called_once_with(True, filename='logfile')
        mock_detect_changes.assert_called_once_with(
            ANY, ANY, 'muri', 1, mongo_repo='repo', progressbar=True)

    @patch('signal_processing.detect_changes.detect_changes')
    @patch('signal_processing.detect_changes.config.ConfigDict', autospec=True)
    @patch('signal_processing.detect_changes.log.setup_logging')
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
            'tid', 'patch', 'muri', None, mongo_repo='../src', progressbar=False)

    @patch('signal_processing.detect_changes.detect_changes')
    @patch('signal_processing.detect_changes.config.ConfigDict', autospec=True)
    @patch('signal_processing.detect_changes.log.setup_logging')
    def test_exception(self, mock_logging, mock_config_dict, mock_detect_changes):
        """
        Test main silently handles errors.
        TODO: remove on completion of PERF-1519 / TIG-1065.

        """
        mock_detect_changes.return_value = (jobs.Job(time.sleep), )
        result = self.runner.invoke(main)
        self.assertEqual(result.exit_code, 2)
        self.assertIn('1 Unexpected Exceptions', result.output)
