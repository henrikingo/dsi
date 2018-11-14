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
        self.assertEquals(test_driver.pool_size, 200)

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

        test_identifiers = ({
            'project': self.sysperf_perf_json['project_id'],
            'variant': self.sysperf_perf_json['variant'],
            'task': self.sysperf_perf_json['task_name'],
            'test': test,
            'thread_level': '1'
        } for test in (u'mixed_insert', u'mixed_insert_bad', u'mixed_findOne'))

        mock_model.db.points.aggregate.return_value = test_identifiers
        mock_model.compute_change_points.return_value = (1, 2, 3)
        test_driver = detect_changes.DetectChangesDriver(self.sysperf_perf_json, self.mongo_uri,
                                                         0.001, 'mongo_repo')
        test_driver.run()
        mock_PointsModel.assert_called_once_with(
            self.mongo_uri, mongo_repo='mongo_repo', credentials=None)

        calls = [
            call(
                mock_model.compute_change_points,
                arguments=(test_identifier, 0.001),
                identifier=test_identifier) for test_identifier in test_identifiers
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

    def _test_get_points(self, limit=None, expected=None):
        with patch('signal_processing.detect_changes.pymongo.MongoClient', autospec=True) \
                as mock_mongo_client:
            test_identifier = {
                'project': self.sysperf_perf_json['project_id'],
                'variant': self.sysperf_perf_json['variant'],
                'task': self.sysperf_perf_json['task_name'],
                'test': 'mixed_insert',
                'thread_level': '1'
            }

            mock_db = MagicMock(name='db', autospec=True)
            mock_cursor = MagicMock(name='cursor', autospec=True)
            mock_mongo_client.return_value.get_database.return_value = mock_db
            if expected is None:
                expected = {key: [] for key in detect_changes.ARRAY_FIELDS}
            mock_db.points.aggregate.return_value = [expected]
            mock_cursor.return_value = self.sysperf_points
            test_model = detect_changes.PointsModel(self.mongo_uri, limit=limit)

            self.assertEqual(expected, test_model.get_points(test_identifier))
            calls = mock_db.points.aggregate.call_args_list
            self.assertTrue(len(calls) == 1)
            pipeline_stages = 6
            if limit is not None:
                pipeline_stages += 1
            self.assertTrue(len(calls[0][0][0]) == pipeline_stages)

    def test_get_points(self):
        self._test_get_points()

    def test_get_points_assertion(self):
        """ test get point asserts invalid sizes. """
        expected = {
            key: range(10) if key != 'create_times' else range(5)
            for key in detect_changes.ARRAY_FIELDS
        }

        with self.assertRaisesRegexp(Exception, 'All array sizes were not equal:'):
            self._test_get_points(expected=expected)

    def test_get_points_custom_limit(self):
        """
        Test that limit is called on cursor when specified.
        """
        self._test_get_points(limit=10)

    def _test_compute_change_points(self, exception=False):
        # pylint: disable=too-many-locals

        with patch('pymongo.InsertOne') as mock_insert,\
             patch('pymongo.DeleteMany') as mock_delete,\
             patch('signal_processing.qhat.get_githashes_in_range_repo'),\
             patch('signal_processing.qhat.QHat', autospec=True) as mock_qhat_class,\
             patch('signal_processing.detect_changes.pymongo.MongoClient') as mock_mongo_client:

            mock_db = MagicMock(name='db', autospec=True)
            thread_level = '4'

            if exception:
                mock_delete.side_effect = [Exception('boom'), "DeleteMany"]
                expected_inserts = [1, 2]
                mock_db.change_points.find.return_value = expected_inserts
            else:
                mock_delete.return_value = "DeleteMany"
                mock_db.change_points.find.return_value = []

                expected_inserts = [
                    OrderedDict([
                        ('project', self.sysperf_perf_json['project_id']),
                        ('variant', self.sysperf_perf_json['variant']),
                        ('task', self.sysperf_perf_json['task_name']),
                        ('test', self.sysperf_perf_json['data']['results'][0]['name']),
                        ('thread_level', thread_level),
                        ('order', i),
                        ('task_id', 'task {}'.format(i)),
                        ('version_id', 'version {}'.format(i))
                    ]) for i in range(1, 3)]   # yapf: disable

            mock_insert.side_effect = ["InsertOne 1", "InsertOne 2"]
            mock_bulk = MagicMock(name='bulk', autospec=True)
            mock_mongo_client.return_value.get_database.return_value = mock_db
            mock_db.change_points.bulk_write.return_value = mock_bulk

            size = 3
            values = range(1, size + 1)
            thread_level_results = {
                'project': self.sysperf_perf_json['project_id'],
                'variant': self.sysperf_perf_json['variant'],
                'task': self.sysperf_perf_json['task_name'],
                'test': self.sysperf_perf_json['data']['results'][0]['name'],
                'thread_level': thread_level,
                'size': size,
                'series': values,
                'revisions': ['revision {}'.format(i) for i in values],
                'orders': values,
                'create_times': values,
                'task_ids': ['task {}'.format(i) for i in values],
                'version_ids': ['version {}'.format(i) for i in values],
            }

            mock_db.points.aggregate.return_value = [thread_level_results]
            mock_qhat = MagicMock(
                name='qhat', autospec=True, change_points=[{
                    'order': 1
                }, {
                    'order': 2
                }])
            mock_qhat_class.return_value = mock_qhat

            test_identifier = {
                'project': self.sysperf_perf_json['project_id'],
                'variant': self.sysperf_perf_json['variant'],
                'task': self.sysperf_perf_json['task_name'],
                'test': self.sysperf_perf_json['data']['results'][0]['name'],
                'thread_level': thread_level
            }

            test_model = detect_changes.PointsModel(self.mongo_uri)
            if exception:
                with self.assertRaises(Exception) as context:
                    test_model.compute_change_points(test_identifier, weighting=0.001)
                self.assertTrue('boom' in context.exception)

                # delete is called twice in this case
                mock_delete.assert_has_calls([call(test_identifier), call(test_identifier)])
            else:
                actual_size, num_change_points = test_model.compute_change_points(
                    test_identifier, weighting=0.001)

                self.assertEqual(actual_size, size)
                self.assertEqual(num_change_points, 2)

                mock_delete.assert_called_once_with(test_identifier)

            mock_db.change_points.find.assert_called_once_with(test_identifier)
            mock_insert.assert_has_calls(
                [call(expected_insert) for expected_insert in expected_inserts])
            mock_mongo_client.return_value.get_database.assert_called_once_with()
            mock_mongo_client.assert_called_once_with(self.mongo_uri)
            mock_db.change_points.bulk_write.assert_called_once_with(
                ["DeleteMany", "InsertOne 1", "InsertOne 2"])
            mock_qhat_class.assert_called_once_with(
                thread_level_results,
                pvalue=None,
                credentials=None,
                mongo_repo=None,
                weighting=0.001)

    def test_compute_change_points(self):
        """ test compute change points. """
        self._test_compute_change_points()

    def test_compute_change_points_rollback(self):
        self._test_compute_change_points(True)

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
