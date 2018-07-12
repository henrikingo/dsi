"""
Unit tests for signal_processing/etl_evg_mongo.py.
"""

import datetime
import os
import unittest
from mock import MagicMock, call, patch

import signal_processing.etl_evg_mongo as etl_evg_mongo
from utils import load_json_file


def _get_load_results_args(histories, version_id=None, start_date=None, reverse=False):
    """
    Find the results from the Evergreen history for a given task that would be used as arguments by
    etl_helpers.load in etl_evg_mongo._etl_evg_mongo given either a `version_id` or a `start_date`.
    """
    if not version_id and not start_date:
        return None
    if reverse:
        for history in histories:
            history.reverse()
    results = []
    seen_task_ids = set()
    for history in histories:
        for result in history:
            if result['task_id'] in seen_task_ids:
                continue
            if start_date and result['create_time'] <= start_date.isoformat():
                results.reverse()
                return results
            if result['version_id'] == version_id:
                results.reverse()
                return results
            seen_task_ids.add(result['task_id'])
            results.append(result)
    results.reverse()
    return results


class TestEtlEvgMongo(unittest.TestCase):
    """
    Test suite for etl_evg_mongo.py methods.
    """

    def setUp(self):
        self.dirname = os.path.dirname(__file__)
        sysperf_file = os.path.join(self.dirname, 'unittest_files/sysperf_history.json')
        micro_file = os.path.join(self.dirname, 'unittest_files/microbenchmarks_history.json')
        self.sysperf_history = load_json_file(sysperf_file)
        self.micro_history = load_json_file(micro_file)
        self.default_history_config = {'sys-perf': None, 'performance': None}
        self.mongo_uri = 'mongo_uri'

    def test__get_project_variant_tasks(self):
        """
        Test that `_get_project_variant_tasks` works with default history configuration.
        """
        expected_file = os.path.join(self.dirname, 'unittest_files/default_flattened.json')
        expected = load_json_file(expected_file)
        mock_evg_client = MagicMock(name='evg_client', autospec=True)
        mock_evg_client.query_project_history.side_effect = [
            self.micro_history, self.sysperf_history
        ]
        actual = etl_evg_mongo._get_project_variant_tasks(mock_evg_client,
                                                          self.default_history_config)
        self.assertEqual(expected, actual)
        calls = [call(project) for project in self.default_history_config]
        mock_evg_client.query_project_history.assert_has_calls(calls)

    def test__get_project_variant_tasks_config(self):
        """
        Test that `get_project_variant_tasks` works with history configured.
        """
        history_config = {
            'sys-perf': {
                'linux-1-node-replSet': None,
                'linux-3-node-replSet': {
                    'bestbuy_agg': None
                }
            }
        }
        expected_file = os.path.join(self.dirname, 'unittest_files/configured_flattened.json')
        expected = load_json_file(expected_file)
        mock_evg_client = MagicMock(name='evg_client', autospec=True)
        mock_evg_client.query_project_history.side_effect = [self.sysperf_history]
        actual = etl_evg_mongo._get_project_variant_tasks(mock_evg_client, history_config)
        self.assertEqual(expected, actual)
        mock_evg_client.query_project_history.assert_called_once_with('sys-perf')

    #pylint: disable=invalid-name
    @patch('signal_processing.etl_evg_mongo.pymongo.MongoClient', autospec=True)
    def test__get_last_version_id(self, mock_MongoClient):
        """
        Test that `_get_last_version_id` correctly querys the most recent version_id in the `points`
        collection for a given task.
        """
        variant = 'linux-standalone'
        task = 'industry_benchmarks'
        docs = [{'version_id': 1}]
        mock_db = MagicMock(name='db', autospec=True)
        mock_MongoClient.return_value.get_database.return_value = mock_db
        mock_db.points.find.return_value.sort.return_value.limit.return_value = iter(docs)
        expected = docs[0]['version_id']
        actual = etl_evg_mongo._get_last_version_id(self.mongo_uri, variant, task)
        self.assertEqual(expected, actual)
        mock_db.points.find.assert_called_once_with({
            'project': {
                '$in': [project for project in self.default_history_config.iterkeys()]
            },
            "task": task,
            'variant': variant
        }, {
            'version_id': True
        })
        mock_db.points.find.return_value.sort.called_once_with('order', -1)
        mock_db.points.find.return_value.sort.return_value.limit.assert_called_once_with(1)

    @patch('signal_processing.etl_evg_mongo.pymongo.MongoClient', autospec=True)
    def test__get_last_version_id_empty_task(self, mock_MongoClient):
        """
        Test that `_get_last_version_id` correctly returns `None` when the `points` collection does
        not have the given task.
        """
        variant = 'linux-standalone'
        task = 'industry_benchmarks'
        docs = []
        mock_db = MagicMock(name='db', autospec=True)
        mock_MongoClient.return_value.get_database.return_value = mock_db
        mock_db.points.find.return_value.sort.return_value.limit.return_value = iter(docs)
        actual = etl_evg_mongo._get_last_version_id(self.mongo_uri, variant, task)
        self.assertEqual(None, actual)

    #pylint: enable=invalid-name

    #pylint: disable=too-many-locals
    @patch('signal_processing.etl_evg_mongo.etl_helpers.load', autospec=True)
    @patch('signal_processing.etl_evg_mongo._get_project_variant_tasks', autospec=True)
    @patch('signal_processing.etl_evg_mongo._get_last_version_id', autospec=True)
    def test__etl_evg_mongo(self, mock__get_last_version_id, mock__get_project_variant_tasks,
                            mock_load):
        """
        Test _etl_evg_mongo wit the default configuration.
        """
        project = 'sys-perf'
        variant = 'linux-standalone'
        task = 'industry_benchmarks'
        history_config = {project: {variant: {task: None}}}
        actual_default_history_config = etl_evg_mongo.DEFAULT_HISTORY_CONFIG
        etl_evg_mongo.DEFAULT_HISTORY_CONFIG = history_config
        version_id = 'sys_perf_353c918ab688cda839bf2efb60f8cab9d078f3da'
        project_variant_tasks = [{
            'task': task,
            'task_id': 'some_task_id',
            'variant': variant,
            'project': project
        }]
        h_file = os.path.join(self.dirname, 'unittest_files/industry_benchmarks_history.json')
        h_file2 = os.path.join(self.dirname, 'unittest_files/industry_benchmarks_history_2.json')
        history = load_json_file(h_file)
        history2 = load_json_file(h_file2)
        mock_evg_client = MagicMock(name='evg_client', autospec=True)
        mock_evg_client.query_mongo_perf_task_history.side_effect = [history, history2]
        mock__get_last_version_id.return_value = version_id
        mock__get_project_variant_tasks.return_value = project_variant_tasks
        etl_evg_mongo._etl_evg_mongo(mock_evg_client, self.mongo_uri)
        mock__get_project_variant_tasks.assert_called_once_with(mock_evg_client, history_config)
        mock__get_last_version_id.assert_called_once_with(self.mongo_uri, variant, task)
        query_calls = [
            call(task, project_variant_tasks[0]['task_id']),
            call(task, history[-1]['task_id'])
        ]
        mock_evg_client.query_mongo_perf_task_history.assert_has_calls(query_calls)
        load_calls = [
            call(result, self.mongo_uri, None)
            for result in _get_load_results_args([history, history2], version_id=version_id)
        ]
        mock_load.assert_has_calls(load_calls)
        etl_evg_mongo.DEFAULT_HISTORY_CONFIG = actual_default_history_config

    @patch('signal_processing.etl_evg_mongo.etl_helpers.load', autospec=True)
    @patch('signal_processing.etl_evg_mongo._get_project_variant_tasks', autospec=True)
    @patch('signal_processing.etl_evg_mongo._get_last_version_id', autospec=True)
    def test__etl_evg_mongo_empty(self, mock__get_last_version_id, mock__get_project_variant_tasks,
                                  mock_load):
        """
        Test _etl_evg_mongo with an empty `points` collection.
        """
        actual_start_date = etl_evg_mongo.START_DATE
        etl_evg_mongo.START_DATE = datetime.datetime(2018, 3, 30)
        project = 'sys-perf'
        variant = 'linux-standalone'
        task = 'industry_benchmarks'
        history_config = {project: {variant: {task: None}}}
        project_variant_tasks = [{
            'task': task,
            'task_id': 'some_task_id',
            'variant': variant,
            'project': project
        }]
        h_file = os.path.join(self.dirname, 'unittest_files/industry_benchmarks_history.json')
        history = load_json_file(h_file)
        mock_evg_client = MagicMock(name='evg_client', autospec=True)
        mock_evg_client.query_mongo_perf_task_history.return_value = history
        mock__get_last_version_id.return_value = None
        mock__get_project_variant_tasks.return_value = project_variant_tasks
        etl_evg_mongo._etl_evg_mongo(mock_evg_client, self.mongo_uri, history_config)
        mock_evg_client.query_mongo_perf_task_history.called_once_with(
            task, project_variant_tasks[0]['task_id'])
        load_calls = [
            call(result, self.mongo_uri, None)
            for result in _get_load_results_args([history], start_date=etl_evg_mongo.START_DATE)
        ]
        mock_load.assert_has_calls(load_calls)
        etl_evg_mongo.START_DATE = actual_start_date

    @patch('signal_processing.etl_evg_mongo.etl_helpers.load', autospec=True)
    @patch('signal_processing.etl_evg_mongo._get_project_variant_tasks', autospec=True)
    @patch('signal_processing.etl_evg_mongo._get_last_version_id', autospec=True)
    def test__etl_evg_mongo_tests(self, mock__get_last_version_id, mock__get_project_variant_tasks,
                                  mock_load):
        """
        Test _etl_evg_mongo with tests excluded.
        """
        project = 'sys-perf'
        variant = 'linux-standalone'
        task = 'industry_benchmarks'
        tests = ['ycsb_load']
        test_set = set([test for test in tests])
        history_config = {project: {variant: {task: tests}}}
        version_id = 'sys_perf_353c918ab688cda839bf2efb60f8cab9d078f3da'
        project_variant_tasks = [{
            'task': task,
            'task_id': 'some_task_id',
            'variant': variant,
            'project': project
        }]
        h_file = os.path.join(self.dirname, 'unittest_files/industry_benchmarks_history.json')
        h_file2 = os.path.join(self.dirname, 'unittest_files/industry_benchmarks_history_2.json')
        history = load_json_file(h_file)
        history2 = load_json_file(h_file2)
        mock_evg_client = MagicMock(name='evg_client', autospec=True)
        mock_evg_client.query_mongo_perf_task_history.side_effect = [history, history2]
        mock__get_last_version_id.return_value = None
        mock__get_project_variant_tasks.return_value = project_variant_tasks
        etl_evg_mongo._etl_evg_mongo(mock_evg_client, self.mongo_uri, history_config)
        load_calls = [
            call(result, self.mongo_uri, test_set)
            for result in _get_load_results_args([history, history2], version_id=version_id)
        ]
        mock_load.assert_has_calls(load_calls)

    #pylint: disable=too-many-locals
