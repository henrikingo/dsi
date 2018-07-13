"""
Unit tests for signal_processing/detect_changes.py.
"""

import os
import unittest
from collections import OrderedDict
from mock import ANY, MagicMock, call, patch

import signal_processing.detect_changes as detect_changes
from sp_utils import load_json_file


# pylint: disable=invalid-name
class TestDetectChangesDriver(unittest.TestCase):
    """
    Test suite for the DetectChangesDriver class.
    """

    def setUp(self):
        self.mongo_uri = 'mongodb+srv://fake@dummy-server.mongodb.net/perf'
        dirname = os.path.dirname(__file__)
        sysperf_perf_file = os.path.join(dirname, 'unittest_files/sysperf_perf.json')
        sysperf_points_file = os.path.join(dirname, 'unittest_files/sysperf_points.json')
        self.sysperf_perf_json = load_json_file(sysperf_perf_file)
        self.sysperf_points = load_json_file(sysperf_points_file)

    @patch('signal_processing.detect_changes.DetectChangesDriver._print_result', autospec=True)
    @patch('signal_processing.detect_changes.PointsModel', autospec=True)
    def test_run(self, mock_PointsModel, mock__print_result):
        tests = set(['mixed_insert', 'mixed_findOne'])
        mock_model = mock_PointsModel.return_value
        mock_model.compute_change_points.return_value = (1, 2, 3)
        test_driver = detect_changes.DetectChangesDriver(self.sysperf_perf_json, self.mongo_uri)
        test_driver.run()
        mock_PointsModel.assert_called_once_with(self.sysperf_perf_json, self.mongo_uri)
        compute_change_points_calls = [call(test) for test in tests]
        mock_model.compute_change_points.assert_has_calls(
            compute_change_points_calls, any_order=True)
        print_result_calls = [call(test_driver, 1, 2, 3, test) for test in tests]
        mock__print_result.assert_has_calls(print_result_calls, any_order=True)


class TestPointsModel(unittest.TestCase):
    """
    Test suite for the PointsModel class.
    """

    def setUp(self):
        self.mongo_uri = 'mongodb+srv://fake@dummy-server.mongodb.net/perf'
        dirname = os.path.dirname(__file__)
        sysperf_perf_file = os.path.join(dirname, 'unittest_files/sysperf_perf.json')
        sysperf_points_file = os.path.join(dirname, 'unittest_files/sysperf_points.json')
        self.sysperf_perf_json = load_json_file(sysperf_perf_file)
        self.sysperf_points = load_json_file(sysperf_points_file)

    @patch('signal_processing.detect_changes.pymongo.MongoClient', autospec=True)
    def test_get_points(self, mock_MongoClient):
        expected_query = OrderedDict(
            [('project', self.sysperf_perf_json['project_id']),
             ('variant', self.sysperf_perf_json['variant']), ('task',
                                                              self.sysperf_perf_json['task_name']),
             ('test', self.sysperf_perf_json['data']['results'][0]['name'])])
        expected_projection = {'results': 1, 'revision': 1, 'order': 1, 'create_time': 1, '_id': 0}
        expected_series = {}
        expected_revisions = {}
        expected_orders = {}
        expected_create_times = {}
        expected_num_points = 0
        for point in self.sysperf_points:
            for result in point['results']:
                if result['thread_level'] in expected_series:
                    expected_series[result['thread_level']].append(result['ops_per_sec'])
                    expected_revisions[result['thread_level']].append(point['revision'])
                    expected_orders[result['thread_level']].append(point['order'])
                    expected_create_times[result['thread_level']].append(point['create_time'])
                else:
                    expected_series[result['thread_level']] = [result['ops_per_sec']]
                    expected_revisions[result['thread_level']] = [point['revision']]
                    expected_orders[result['thread_level']] = [point['order']]
                    expected_create_times[result['thread_level']] = [point['create_time']]
                expected_num_points += 1
        mock_db = MagicMock(name='db', autospec=True)
        mock_cursor = MagicMock(name='cursor', autospec=True)
        mock_MongoClient.return_value.get_database.return_value = mock_db
        mock_db.points.find.return_value.sort = mock_cursor
        mock_cursor.return_value = self.sysperf_points
        test_model = detect_changes.PointsModel(self.sysperf_perf_json, self.mongo_uri)
        actual = test_model.get_points(self.sysperf_perf_json['data']['results'][0]['name'])
        self.assertEqual(actual, (expected_series, expected_revisions, expected_orders,
                                  expected_query, expected_create_times, expected_num_points))
        mock_MongoClient.assert_called_once_with(self.mongo_uri)
        mock_MongoClient.return_value.get_database.assert_called_once_with()
        mock_db.points.find.assert_called_once_with(expected_query, expected_projection)
        mock_db.points.find.return_value.sort.assert_called_once_with([('order', 1)])

    @patch('signal_processing.detect_changes.pymongo.MongoClient', autospec=True)
    def test_get_points_custom_limit(self, mock_MongoClient):
        """
        Test that limit is called on cursor when specified.
        """
        limit = 10
        mock_db = MagicMock(name='db', autospec=True)
        mock_cursor = MagicMock(name='cursor', autospec=True)
        mock_MongoClient.return_value.get_database.return_value = mock_db
        mock_db.points.find.return_value.sort = mock_cursor
        test_model = detect_changes.PointsModel(self.sysperf_perf_json, self.mongo_uri, limit=limit)
        test_model.get_points(self.sysperf_perf_json['data']['results'][0]['name'])
        mock_cursor.return_value.limit.assert_called_with(limit)

    @patch('signal_processing.detect_changes.QHat', autospec=True)
    @patch('signal_processing.detect_changes.PointsModel.get_points', autospec=True)
    @patch('signal_processing.detect_changes.pymongo.MongoClient', autospec=True)
    def test_compute_change_points(self, mock_MongoClient, mock_get_points, mock_QHat):
        expected_query = OrderedDict(
            [('project', self.sysperf_perf_json['project_id']),
             ('variant', self.sysperf_perf_json['variant']), ('task',
                                                              self.sysperf_perf_json['task_name']),
             ('test', self.sysperf_perf_json['data']['results'][0]['name'])])
        mock_db = MagicMock(name='db', autospec=True)
        mock_bulk = MagicMock(name='bulk', autospec=True)
        mock_MongoClient.return_value.get_database.return_value = mock_db
        mock_db.change_points.initialize_ordered_bulk_op.return_value = mock_bulk
        mock_get_points.return_value = [{
            4: []
        }, {
            4: []
        }, {
            4: []
        }, expected_query, {
            4: []
        }, 'many_points']
        test = self.sysperf_perf_json['data']['results'][0]['name']
        test_model = detect_changes.PointsModel(self.sysperf_perf_json, self.mongo_uri)
        actual = test_model.compute_change_points(test)
        mock_QHat.assert_called_once_with(
            {
                'series': [],
                'revisions': [],
                'orders': [],
                'create_times': [],
                'testname': test,
                'thread_level': 4
            },
            pvalue=None)
        mock_db.change_points.initialize_ordered_bulk_op.assert_called_once()
        mock_bulk.find.assert_called_once_with(expected_query)
        mock_bulk.find.return_value.remove.assert_called_once()
        mock_bulk.execute.assert_called_once()
        self.assertEqual(actual, ('many_points', 0, ANY))
        mock_MongoClient.assert_called_once_with(self.mongo_uri)
        mock_MongoClient.return_value.get_database.assert_called_once_with()

    @patch('signal_processing.detect_changes.QHat', autospec=True)
    @patch('signal_processing.detect_changes.PointsModel.get_points', autospec=True)
    @patch('signal_processing.detect_changes.pymongo.MongoClient', autospec=True)
    def test_compute_change_points_thread_level(self, mock_MongoClient, mock_get_points, mock_QHat):
        """
        Test compute_change_points when a point has multiple thread levels.
        """
        mock_get_points.return_value = [{
            4: [1, 2, 3],
            16: [3]
        }, {
            4: ['abc', 'bcd', 'cde'],
            16: ['cde']
        }, {
            4: [0, 1, 2],
            16: [2]
        }, {'query'}, {
            4: [1, 2, 3],
            16: [3]
        }, 'many_points']
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
                pvalue=None),
            call(
                {
                    'series': [3],
                    'revisions': ['cde'],
                    'orders': [2],
                    'create_times': [3],
                    'testname': test,
                    'thread_level': 16
                },
                pvalue=None)
        ]
        test_model = detect_changes.PointsModel(self.sysperf_perf_json, self.mongo_uri)
        test_model.compute_change_points(test)
        self.assertTrue(qhat_calls < mock_QHat.mock_calls)

    @patch('signal_processing.detect_changes.config.ConfigDict', autospec=True)
    @patch('signal_processing.detect_changes.evergreen_client.Client', autospec=True)
    def test_detect_changes(self, mock_evg_Client, mock_ConfigDict):
        """
        Test the main function (second only to literal main) of detect_changes
        """
        detect_changes.detect_changes()
        mock_evg_Client.assert_called_once()
        mock_ConfigDict.assert_called_once()
