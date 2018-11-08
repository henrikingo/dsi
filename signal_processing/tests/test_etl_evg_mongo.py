"""
Unit tests for signal_processing/etl_evg_mongo.py.
"""
import datetime
import os
import unittest
from collections import OrderedDict

from mock import MagicMock, call, patch

import signal_processing.etl_evg_mongo as etl_evg_mongo
from test_lib.fixture_files import FixtureFiles

FIXTURE_FILES = FixtureFiles(os.path.dirname(__file__))


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


class TestGetProjectVariantTask(unittest.TestCase):
    """
    Test suite for etl_evg_mongo._get_project_variant_tasks.
    """

    def setUp(self):
        self.sysperf_history = FIXTURE_FILES.load_json_file('sysperf_history.json')
        self.micro_history = FIXTURE_FILES.load_json_file('microbenchmarks_history.json')
        self.default_history_config = OrderedDict([('sys-perf', None), ('performance', None)])
        self.mongo_uri = 'mongo_uri'

    def test__get_project_variant_tasks(self):
        """
        Test that `_get_project_variant_tasks` works with default history configuration.
        """
        expected = FIXTURE_FILES.load_json_file('default_flattened.json')
        mock_evg_client = MagicMock(name='evg_client', autospec=True)
        mock_evg_client.query_project_history.return_value = self.sysperf_history
        project = 'sys-perf'
        actual = etl_evg_mongo._get_project_variant_tasks(mock_evg_client, project)
        self.assertListEqual(expected, actual)
        mock_evg_client.query_project_history.assert_called_once_with(project)


class TestGetLastVersionId(unittest.TestCase):
    """
    Test suite for etl_evg_mongo._get_last_version_id.
    """

    def setUp(self):
        self.sysperf_history = FIXTURE_FILES.load_json_file('sysperf_history.json')
        self.micro_history = FIXTURE_FILES.load_json_file('microbenchmarks_history.json')
        self.default_history_config = OrderedDict([('sys-perf', None), ('performance', None)])
        self.mongo_uri = 'mongo_uri'

    #pylint: disable=invalid-name
    @patch('signal_processing.etl_evg_mongo.pymongo.MongoClient', autospec=True)
    def test__get_last_version_id(self, mock_MongoClient):
        """
        Test that `_get_last_version_id` correctly querys the most recent version_id in the `points`
        collection for a given task.
        """
        variant = 'linux-standalone'
        task = 'industry_benchmarks'
        project = 'sys-perf'
        docs = [{'version_id': 1}]
        mock_db = MagicMock(name='db', autospec=True)
        mock_MongoClient.return_value.get_database.return_value = mock_db
        mock_db.points.find.return_value.sort.return_value.limit.return_value = iter(docs)
        expected = docs[0]['version_id']
        actual = etl_evg_mongo._get_last_version_id(self.mongo_uri, variant, task, project)
        self.assertEqual(expected, actual)
        mock_db.points.find.assert_called_once_with({
            'project': project,
            'task': task,
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
        project = 'sys-perf'
        variant = 'linux-standalone'
        task = 'industry_benchmarks'
        docs = []
        mock_db = MagicMock(name='db', autospec=True)
        mock_MongoClient.return_value.get_database.return_value = mock_db
        mock_db.points.find.return_value.sort.return_value.limit.return_value = iter(docs)

        actual = etl_evg_mongo._get_last_version_id(self.mongo_uri, variant, task, project)
        self.assertEqual(None, actual)


def flatten(tasks):
    """
    Helper to flatten a list of lists.
    :param list(list) tasks: The list of lists.
    :return: A single level list.
    """
    return [item for sublist in tasks for item in sublist]


class TestGetTaskIdentifiers(unittest.TestCase):
    """
    Test suite for etl_evg_mongo._get_task_identifiers.
    """

    def setUp(self):
        self.sysperf_history = FIXTURE_FILES.load_json_file('sysperf_history.json')
        self.micro_history = FIXTURE_FILES.load_json_file('microbenchmarks_history.json')
        self.default_history_config = OrderedDict([('sys-perf', None), ('performance', None)])
        self.mongo_uri = 'mongo_uri'

    def _test_projects(self, projects=(), exceptions=()):
        """
        _etl_evg_mongo helper.
        """
        #pylint: disable=invalid-name
        projects = list(projects)
        with patch('signal_processing.etl_evg_mongo._get_project_variant_tasks')\
            as mock__get_project_variant_tasks, \
             patch('signal_processing.commands.jobs.Job', autospec=True)\
            as mock_job_cls, \
            patch('signal_processing.commands.jobs.process_jobs', autospec=True)\
                    as mock_process_jobs:

            mock_evg_client = MagicMock(name='evg_client', autospec=True)
            mock__get_project_variant_tasks.return_value = []

            mock_jobs = [
                MagicMock(
                    name=project,
                    autospec=True,
                    exception=exceptions[i] if i < len(exceptions) else None,
                    identifier=project,
                    result=[project]) for i, project in enumerate(projects)
            ]
            for mock_job in mock_jobs:
                mock_job.return_value = mock_job
            mock_job_cls.side_effect = mock_jobs
            mock_process_jobs.return_value = mock_jobs

            first_exception = next((exception for exception in exceptions if exception is not None),
                                   None)
            if first_exception is not None:
                with self.assertRaises(Exception) as context:
                    etl_evg_mongo._get_task_identifiers(mock_evg_client, projects, False, 1)
                self.assertTrue(str(first_exception) in context.exception)
            else:
                actual = etl_evg_mongo._get_task_identifiers(mock_evg_client, projects, False, 1)
                self.assertEqual(actual, projects)
            mock_job_cls.assert_has_calls([
                call(
                    mock__get_project_variant_tasks,
                    arguments=(mock_evg_client, project),
                    identifier=project) for project in projects
            ])

            mock_evg_client.query_mongo_perf_task_history.assert_not_called()

    #pylint: enable=invalid-name
    def test_no_projects(self):
        """
        Test _get_task_identifiers  with no projects.
        """
        self._test_projects()

    def test_2_projects(self):
        """
        Test _get_task_identifiers with multiple project and no tasks.
        """
        self._test_projects(['project1', 'project2'])

    def test_10_projects(self):
        """
        Test _get_task_identifiers with multiple project and no tasks.
        """
        self._test_projects(['project{}'.format(i) for i in range(10)])

    def test_exceptions(self):
        """
        Test _get_task_identifiers with exceptions.
        """
        self._test_projects(
            ['projects{}'.format(i) for i in range(10)], exceptions=[None, Exception("first")])

    def test_multiple_process(self):
        """
        Test _etl_evg_mongo with multiple processes.
        """
        pool_size = 2
        with patch('signal_processing.etl_evg_mongo._get_project_variant_tasks')\
            as mock__get_project_variant_tasks, \
             patch('signal_processing.commands.jobs.process_jobs', autospec=True)\
            as mock_process_jobs:

            mock_evg_client = MagicMock(name='evg_client', autospec=True)
            mock__get_project_variant_tasks.return_value = []
            etl_evg_mongo._get_task_identifiers(mock_evg_client, [], False, pool_size)
        _, kwargs = mock_process_jobs.call_args
        self.assertEquals(kwargs['pool_size'], pool_size)


class TestEtlEvgMongo(unittest.TestCase):
    """
    Test suite for etl_evg_mongo._etl_evg_mongo.
    """

    def setUp(self):
        self.sysperf_history = FIXTURE_FILES.load_json_file('sysperf_history.json')
        self.micro_history = FIXTURE_FILES.load_json_file('microbenchmarks_history.json')
        self.default_history_config = OrderedDict([('sys-perf', None), ('performance', None)])
        self.mongo_uri = 'mongo_uri'

    def _test_projects(self, task_identifiers=(), exceptions=()):
        """
        _etl_evg_mongo helper.
        """
        #pylint: disable=invalid-name
        if task_identifiers:
            task_identifiers = [{'task': task} for task in task_identifiers]
        with patch('signal_processing.etl_evg_mongo._get_task_identifiers')\
                as mock__get_task_identifiers, \
            patch('signal_processing.etl_evg_mongo._etl_single_task')\
                as mock__etl_single_task, \
             patch('signal_processing.commands.jobs.Job', autospec=True)\
            as mock_job_cls, \
             patch('signal_processing.commands.jobs.process_jobs', autospec=True)\
            as mock_job_process_jobs:
            mock_evg_client = MagicMock(name='evg_client', autospec=True)
            mock__get_task_identifiers.return_value = task_identifiers
            mock_job_process_jobs.return_value = ()
            mock_jobs = [
                MagicMock(
                    name=task['task'],
                    autospec=True,
                    exception=exceptions[i] if i < len(exceptions) else None,
                    identifier=task,
                    result=task['task']) for i, task in enumerate(task_identifiers)
            ]
            for mock_job in mock_jobs:
                mock_job.return_value = mock_job
            mock_job_cls.side_effect = mock_jobs
            mock_job_process_jobs.return_value = mock_jobs

            results = etl_evg_mongo._etl_evg_mongo(mock_evg_client, self.mongo_uri,
                                                   task_identifiers, False, 1)
            self.assertEquals(results, [job for job in mock_jobs if job.exception])
            mock_job_cls.assert_has_calls([
                call(
                    mock__etl_single_task,
                    arguments=(mock_evg_client, self.mongo_uri, task),
                    identifier=task) for task in task_identifiers
            ])

    #pylint: enable=invalid-name
    def test_no_tasks(self):
        """
        Test _etl_evg_mongo  with no tasks.
        """
        self._test_projects()

    def test_1_task(self):
        """
        Test _etl_evg_mongo with with a single tasks.
        """
        self._test_projects(['task1'])

    def test_10_projects(self):
        """
        Test _etl_evg_mongo with multiple tasks.
        """
        self._test_projects(['task{}'.format(i) for i in range(10)])

    def test_exceptions(self):
        """
        Test _etl_evg_mongo with exceptions.
        """
        self._test_projects(
            ['task{}'.format(i) for i in range(10)], exceptions=[None, Exception("first")])

    def test_multiple_process(self):
        """
        Test _etl_evg_mongo with multiple processes.
        """
        pool_size = 2
        with patch('signal_processing.etl_evg_mongo._get_task_identifiers')\
            as mock__get_project_variant_tasks, \
                patch('signal_processing.commands.jobs.process_jobs', autospec=True) \
                        as mock_process_jobs:

            mock_evg_client = MagicMock(name='evg_client', autospec=True)
            mock__get_project_variant_tasks.return_value = []
            etl_evg_mongo._etl_evg_mongo(mock_evg_client, self.mongo_uri, [], False, pool_size)
            _, kwargs = mock_process_jobs.call_args
            self.assertEquals(kwargs['pool_size'], pool_size)


class TestEtlSingleTask(unittest.TestCase):
    """
    Test suite for etl_evg_mongo._etl_single_task method.
    """

    def setUp(self):
        self.sysperf_history = FIXTURE_FILES.load_json_file('sysperf_history.json')
        self.micro_history = FIXTURE_FILES.load_json_file('microbenchmarks_history.json')
        self.default_history_config = OrderedDict([('sys-perf', None), ('performance', None)])
        self.mongo_uri = 'mongo_uri'

    @patch('signal_processing.etl_evg_mongo.etl_helpers.load', autospec=True)
    @patch('signal_processing.etl_evg_mongo._get_last_version_id', autospec=True)
    def test__etl_evg_mongo_empty(
            self,
            mock__get_last_version_id,
            # mock__get_project_variant_tasks,
            mock_load):
        """
        Test _etl_evg_mongo with an empty `points` collection.
        """
        actual_start_date = etl_evg_mongo.START_DATE
        etl_evg_mongo.START_DATE = datetime.datetime(2018, 3, 30)
        project = 'sys-perf'
        variant = 'linux-standalone'
        task = 'industry_benchmarks'
        project_variant_task = {
            'task': task,
            'task_id': 'some_task_id',
            'variant': variant,
            'project': project
        }
        history = FIXTURE_FILES.load_json_file('industry_benchmarks_history.json')
        mock_evg_client = MagicMock(name='evg_client', autospec=True)
        mock_evg_client.query_mongo_perf_task_history.return_value = history
        mock__get_last_version_id.return_value = None
        etl_evg_mongo._etl_single_task(mock_evg_client, self.mongo_uri, project_variant_task)
        mock_evg_client.query_mongo_perf_task_history.called_once_with(
            task, project_variant_task['task_id'])

        load_calls = [
            call(result, self.mongo_uri)
            for result in _get_load_results_args([history], start_date=etl_evg_mongo.START_DATE)
        ]
        mock_load.assert_has_calls(load_calls)
        etl_evg_mongo.START_DATE = actual_start_date

    @patch('signal_processing.etl_evg_mongo.etl_helpers.load')
    @patch('signal_processing.etl_evg_mongo._get_project_variant_tasks', autospec=True)
    @patch('signal_processing.etl_evg_mongo._get_last_version_id', autospec=True)
    def test_already_seen(self, mock__get_last_version_id, mock__get_project_variant_tasks,
                          mock_load):
        """
        Test _etl_evg_mongo already seen.
        """
        project_variant_task = {
            'task': 'task',
            'task_id': 'some_task_id',
            'variant': "variant",
            'project': "project"
        }

        history = FIXTURE_FILES.load_json_file('industry_benchmarks_history.json')[0:1]
        mock_evg_client = MagicMock(name='evg_client', autospec=True)
        mock_evg_client.query_mongo_perf_task_history.side_effect = [history]
        mock__get_last_version_id.return_value = history[0]['version_id']
        mock__get_project_variant_tasks.return_value = project_variant_task

        etl_evg_mongo._etl_single_task(mock_evg_client, self.mongo_uri, project_variant_task)
        mock_load.assert_not_called()

    @patch('signal_processing.etl_evg_mongo.etl_helpers.load')
    @patch('signal_processing.etl_evg_mongo._get_project_variant_tasks', autospec=True)
    @patch('signal_processing.etl_evg_mongo._get_last_version_id', autospec=True)
    def test_load_one_test(self, mock__get_last_version_id, mock__get_project_variant_tasks,
                           mock_load):
        """
        Test _etl_evg_mongo with at least one test.
        """
        project_variant_task = {
            'task': 'industry_benchmarks',
            'task_id': 'some_task_id',
            'variant': 'linux-standalone',
            'project': 'sys-perf'
        }

        # history is reversed so seen version id is first and loaded
        # is everything but the first
        history = FIXTURE_FILES.load_json_file('industry_benchmarks_history.json')[0:2]

        mock_evg_client = MagicMock(name='evg_client', autospec=True)
        mock_evg_client.query_mongo_perf_task_history.side_effect = [history[:]]
        mock__get_last_version_id.return_value = history[0]['version_id']
        mock__get_project_variant_tasks.return_value = project_variant_task

        etl_evg_mongo._etl_single_task(mock_evg_client, self.mongo_uri, project_variant_task)
        mock_load.assert_called_once_with(history[1], self.mongo_uri)

    @patch('signal_processing.etl_evg_mongo.etl_helpers.load')
    @patch('signal_processing.etl_evg_mongo._get_project_variant_tasks', autospec=True)
    @patch('signal_processing.etl_evg_mongo._get_last_version_id', autospec=True)
    def test_load_multiple_test(self, mock__get_last_version_id, mock__get_project_variant_tasks,
                                mock_load):
        """
        Test _etl_evg_mongo load multiple.
        """
        project_variant_task = {
            'task': 'industry_benchmarks',
            'task_id': 'some_task_id',
            'variant': 'linux-standalone',
            'project': 'sys-perf'
        }

        # history is reversed so seen version id is first and loaded
        # is everything but the first
        history = FIXTURE_FILES.load_json_file('industry_benchmarks_history.json')[0:3]

        mock_evg_client = MagicMock(name='evg_client', autospec=True)
        # pass in a copy of the array as it is reversed in place
        mock_evg_client.query_mongo_perf_task_history.side_effect = [history[:]]
        mock__get_last_version_id.return_value = history[0]['version_id']
        mock__get_project_variant_tasks.return_value = project_variant_task
        etl_evg_mongo._etl_single_task(mock_evg_client, self.mongo_uri, project_variant_task)
        load_calls = [call(result, self.mongo_uri) for result in history[1:]]
        mock_load.assert_has_calls(load_calls)

    @patch('signal_processing.etl_evg_mongo.etl_helpers.load')
    @patch('signal_processing.etl_evg_mongo._get_project_variant_tasks', autospec=True)
    @patch('signal_processing.etl_evg_mongo._get_last_version_id', autospec=True)
    def test_load_full_batch(self, mock__get_last_version_id, mock__get_project_variant_tasks,
                             mock_load):
        """
        Test _etl_evg_mongo load single batch.
        """
        project_variant_task = {
            'task': 'industry_benchmarks',
            'task_id': 'some_task_id',
            'variant': 'linux-standalone',
            'project': 'sys-perf'
        }

        # history is reversed so seen version id is first and loaded
        # is everything but the first
        history = FIXTURE_FILES.load_json_file('industry_benchmarks_history.json')
        mock_evg_client = MagicMock(name='evg_client', autospec=True)
        # pass in a copy of the array as it is reversed in place
        # evergreen returns the last tranche again
        mock_evg_client.query_mongo_perf_task_history.side_effect = [history[:], history[:]]
        mock__get_last_version_id.return_value = 'dummy_version_id'
        mock__get_project_variant_tasks.return_value = project_variant_task

        etl_evg_mongo._etl_single_task(mock_evg_client, self.mongo_uri, project_variant_task)
        load_calls = [call(result, self.mongo_uri) for result in history]
        mock_load.assert_has_calls(load_calls, any_order=True)

    @patch('signal_processing.etl_evg_mongo.etl_helpers.load')
    @patch('signal_processing.etl_evg_mongo._get_project_variant_tasks', autospec=True)
    @patch('signal_processing.etl_evg_mongo._get_last_version_id', autospec=True)
    def test_load_multiple_batches(self, mock__get_last_version_id, mock__get_project_variant_tasks,
                                   mock_load):
        """
        Test _etl_evg_mongo load multiple batches.
        """
        project_variant_task = {
            'task': 'industry_benchmarks',
            'task_id': 'some_task_id',
            'variant': 'linux-standalone',
            'project': 'sys-perf'
        }

        # history is reversed so seen version id is first and loaded
        # is everything but the first
        history1 = FIXTURE_FILES.load_json_file('industry_benchmarks_history.json')[0:2]
        history2 = FIXTURE_FILES.load_json_file('industry_benchmarks_history_2.json')[0:1]
        mock_evg_client = MagicMock(name='evg_client', autospec=True)
        # pass in a copy of the array as it is reversed in place
        mock_evg_client.query_mongo_perf_task_history.side_effect = [history1[:], history2[:]]

        version_id = history2[0]['version_id']
        mock__get_last_version_id.return_value = version_id
        mock__get_project_variant_tasks.return_value = project_variant_task

        etl_evg_mongo._etl_single_task(mock_evg_client, self.mongo_uri, project_variant_task)
        load_calls = [
            call(result, self.mongo_uri)
            for result in _get_load_results_args([history1, history2], version_id=version_id)
        ]
        mock_load.assert_has_calls(load_calls, any_order=True)

    @patch('signal_processing.etl_evg_mongo.etl_helpers.load')
    @patch('signal_processing.etl_evg_mongo._get_project_variant_tasks', autospec=True)
    @patch('signal_processing.etl_evg_mongo._get_last_version_id', autospec=True)
    def test_load_no_previous(self, mock__get_last_version_id, mock__get_project_variant_tasks,
                              mock_load):
        """
        Test _etl_evg_mongo load one batches with no previous version id.
        """
        project_variant_task = {
            'task': 'industry_benchmarks',
            'task_id': 'some_task_id',
            'variant': 'linux-standalone',
            'project': 'sys-perf'
        }

        # history is reversed so seen version id is first and loaded
        # is everything but the first
        history = FIXTURE_FILES.load_json_file('industry_benchmarks_history.json')
        mock_evg_client = MagicMock(name='evg_client', autospec=True)
        # pass in a copy of the array as it is reversed in place
        mock_evg_client.query_mongo_perf_task_history.side_effect = [history[:], None]

        version_id = None
        mock__get_last_version_id.return_value = version_id
        mock__get_project_variant_tasks.return_value = project_variant_task

        etl_evg_mongo._etl_single_task(mock_evg_client, self.mongo_uri, project_variant_task)
        load_calls = [
            call(result, self.mongo_uri)
            for result in _get_load_results_args([history], version_id='dummy')
        ]
        mock_load.assert_has_calls(load_calls, any_order=True)

    @patch('signal_processing.etl_evg_mongo.etl_helpers.load')
    @patch('signal_processing.etl_evg_mongo._get_project_variant_tasks', autospec=True)
    @patch('signal_processing.etl_evg_mongo._get_last_version_id', autospec=True)
    def test_load_batches_no_previous(self, mock__get_last_version_id,
                                      mock__get_project_variant_tasks, mock_load):
        """
        Test _etl_evg_mongo load multiple batches with no previous version id.
        """
        project_variant_task = {
            'task': 'industry_benchmarks',
            'task_id': 'some_task_id',
            'variant': 'linux-standalone',
            'project': 'sys-perf'
        }

        # history is reversed so seen version id is first and loaded
        # is everything but the first
        history1 = FIXTURE_FILES.load_json_file('industry_benchmarks_history.json')
        history2 = FIXTURE_FILES.load_json_file('industry_benchmarks_history_2.json')
        mock_evg_client = MagicMock(name='evg_client', autospec=True)

        # pass in a copy of the array as it is reversed in place
        mock_evg_client.query_mongo_perf_task_history.side_effect = [
            history1[:], history2[:], history2[:]
        ]

        version_id = None
        mock__get_last_version_id.return_value = version_id
        mock__get_project_variant_tasks.return_value = project_variant_task

        etl_evg_mongo._etl_single_task(mock_evg_client, self.mongo_uri, project_variant_task)

        expected = _get_load_results_args(
            [history1, history2],
            version_id=version_id,
            start_date=etl_evg_mongo.START_DATE,
            reverse=True)
        load_calls = [call(result, self.mongo_uri) for result in expected]
        mock_load.assert_has_calls(load_calls, any_order=True)
