"""
Unit tests for signal_processing/etl_helpers.py.
"""

import os
import unittest
from mock import MagicMock, patch
from testfixtures import LogCapture

import pymongo
import structlog
import signal_processing.etl_helpers as etl_helpers
from test_lib.fixture_files import FixtureFiles

FIXTURE_FILES = FixtureFiles(os.path.dirname(__file__))


# pylint: disable=invalid-name
def ns(name):
    return 'signal_processing.etl_helpers.' + name


def create_update(point, result):
    """
    Create an update operation for each result.

    :param dict point: The full point data.
    :param dict result: The current result being processed.
    :return: An updateOne with the correct query and update.
    """
    return pymongo.UpdateOne(
        extract_filter(point, result), {
            "$set": {'results.$.' + k: v
                     for k, v in result.items()}
        })


def extract_filter(point, result=None):
    """
    Create a filter for the point and possibly result thread_level.

    :param dict point: The point data.
    :param dict result: The specific result within the point.
    :return: The filter used in the update command.
    """
    query = {k: point[k] for k in ('project', 'variant', 'task', 'test', 'version_id', 'revision')}
    if result is not None:
        query['results.thread_level'] = result['thread_level']
    return query


class TestloadHistory(unittest.TestCase):
    """
    Test suite for load_history.py methods.
    """

    def setUp(self):
        self.mongo_uri = 'mongodb+srv://fake@dummy-server.mongodb.net/perf'
        self.sysperf_perf_json = FIXTURE_FILES.load_json_file('sysperf_perf.json')
        self.microbenchmarks_perf_json = FIXTURE_FILES.load_json_file('microbenchmarks_perf.json')
        self.sysperf_points = FIXTURE_FILES.load_json_file('sysperf_points.json')
        self.microbenchmarks_points = FIXTURE_FILES.load_json_file('microbenchmarks_points.json')
        # Setup logging so that structlog uses stdlib, and LogCapture works
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level, structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.StackInfoRenderer(), structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.dev.ConsoleRenderer(colors=False)
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )

    # pylint: disable=invalid-name
    @patch(ns('pymongo.MongoClient'), autospec=True)
    def test_load(self, mongo_client_mock):
        """
        Test that load works with a standard configuration.
        """
        self.sysperf_perf_json = FIXTURE_FILES.load_json_file('sysperf_perf_small.json')
        self.sysperf_points = FIXTURE_FILES.load_json_file('sysperf_points_small.json')
        db_mock = MagicMock(name='db', autospec=True)
        mongo_client_mock.return_value.get_database.return_value = db_mock

        mock_client = db_mock.client
        mock_session = mock_client.start_session.return_value.__enter__.return_value

        etl_helpers.load(self.sysperf_perf_json, self.mongo_uri)
        mongo_client_mock.assert_called_once_with(self.mongo_uri)
        mongo_client_mock.return_value.get_database.assert_called_once_with()

        point = self.sysperf_points[0]
        query = extract_filter(point)

        insert_operation = point.copy()
        results = insert_operation.pop('results')

        requests = [
            pymongo.UpdateOne(
                query, {"$set": insert_operation,
                        "$setOnInsert": {
                            "results": results
                        }},
                upsert=True)
        ]

        requests += [create_update(point, result) for result in results]

        mock_session.start_transaction.return_value.__enter__.assert_called_once()
        db_mock.points.bulk_write.assert_called_once_with(requests, ordered=True)

    # pylint: disable=invalid-name
    @patch(ns('pymongo.MongoClient'), autospec=True)
    def test_load_no_results(self, mongo_client_mock):
        """
        Test that load works when results are empty.
        """
        self.sysperf_perf_json = FIXTURE_FILES.load_json_file('sysperf_perf_small.json')
        self.sysperf_points = FIXTURE_FILES.load_json_file('sysperf_points_small.json')

        self.sysperf_perf_json['data']['results'] = []
        db_mock = MagicMock(name='db', autospec=True)
        mongo_client_mock.return_value.get_database.return_value = db_mock

        etl_helpers.load(self.sysperf_perf_json, self.mongo_uri)

        db_mock.client.start_session.return_value.__enter__.assert_not_called()

    # pylint: disable=invalid-name
    @patch(ns('pymongo.MongoClient'), autospec=True)
    def test_load_exception(self, mongo_client_mock):
        """
        Test that load raises exceptions.
        """
        self.sysperf_perf_json = FIXTURE_FILES.load_json_file('sysperf_perf_small.json')
        self.sysperf_points = FIXTURE_FILES.load_json_file('sysperf_points_small.json')
        db_mock = MagicMock(name='db', autospec=True)
        mongo_client_mock.return_value.get_database.return_value = db_mock
        db_mock.points.bulk_write.side_effect = Exception('boom')

        self.assertRaisesRegexp(Exception, 'boom', etl_helpers.load, self.sysperf_perf_json,
                                self.mongo_uri)

    @patch(ns('pymongo.MongoClient'), autospec=True)
    def test_load_with_tests(self, mock_MongoClient):
        """
        Test that load works with a `tests` set that exludes at least one test.
        """
        mock_db = MagicMock(name='db', autospec=True)
        mock_MongoClient.return_value.get_database.return_value = mock_db
        tests = set(['mixed_findOne', 'mixed_insert'])
        etl_helpers.load(self.sysperf_perf_json, self.mongo_uri, tests)
        mock_db.points.bulk_write.assert_called_once()
        tests = set(['mixed_insert'])
        del self.sysperf_points[0]
        mock_db.reset_mock()
        etl_helpers.load(self.sysperf_perf_json, self.mongo_uri, tests)
        mock_db.points.bulk_write.assert_called_once()

    def test_make_filter(self):
        self.assertEqual(
            etl_helpers.make_filter(self.sysperf_points[0]), {
                'project': u'sys-perf',
                'revision': u'e31a40ab59fb5c784ff8d15f07c0b811bd54a516',
                'task': u'mixed_workloads_WT',
                'test': u'mixed_findOne',
                'variant': u'wtdevelop-1-node-replSet',
                'version_id': u'sys_perf_e31a40ab59fb5c784ff8d15f07c0b811bd54a516'
            })

    # pylint: enable=invalid-name

    def test__get_thread_levels(self):
        for i, result in enumerate(self.sysperf_perf_json['data']['results']):
            if i < len(self.sysperf_points):
                actual = etl_helpers._get_thread_levels(result)
                self.assertEqual(actual, self.sysperf_points[i]['results'])
        for i, result in enumerate(self.microbenchmarks_perf_json['data']['results']):
            actual = etl_helpers._get_thread_levels(result)
            self.assertEqual(actual, self.microbenchmarks_points[i]['results'])

    def test__get_max_ops_per_sec(self):
        bad_point = {'max_thread_level': None, 'max_ops_per_sec': None}
        for i, result in enumerate(self.sysperf_perf_json['data']['results']):
            point = self.sysperf_points[i] if i < len(self.sysperf_points) else bad_point
            with LogCapture() as log:
                actual = etl_helpers._get_max_ops_per_sec(result)
                if point is bad_point:
                    log.check(
                        (
                            'signal_processing.etl_helpers',
                            'WARNING',
                            u"[warning  ] Invalid thread level value found [signal_processing.etl_helpers] results_item_key=u'-t' thread_level={u'ops_per_sec': 13876.06811527, u'ops_per_sec_values': [13876.06811527]}"  #pylint: disable=line-too-long
                        ), )  # yapf: disable
                else:
                    log.check()
            self.assertEqual(actual, (point['max_thread_level'], point['max_ops_per_sec']))
        for i, result in enumerate(self.microbenchmarks_perf_json['data']['results']):
            point = self.microbenchmarks_points[i]
            actual = etl_helpers._get_max_ops_per_sec(result)
            self.assertEqual(actual, (point['max_thread_level'], point['max_ops_per_sec']))

    def test_extract_tests(self):
        """
        Test that _extract_tests works with a correctly formatted perf.json file.
        """
        tests = set(['mixed_insert', 'mixed_findOne', 'mixed_insert_bad'])
        self.assertEqual(etl_helpers.extract_tests(self.sysperf_perf_json), tests)


class TestMakeUpdates(unittest.TestCase):
    """
    Test suite for make_updates.
    """

    def load(self, file_name):
        sysperf_points = FIXTURE_FILES.load_json_file(file_name)
        return sysperf_points[0]

    def _test(self, point):
        updates = etl_helpers.make_updates(point)

        insert_operation = point.copy()
        results = insert_operation.pop('results') if 'results' in insert_operation else []
        query = extract_filter(point)

        expected = [
            pymongo.UpdateOne(
                query, {"$set": insert_operation,
                        "$setOnInsert": {
                            "results": results
                        }},
                upsert=True)
        ]

        expected += [create_update(point, result) for result in results]
        self.assertEquals(updates, expected)

    def test_no_results(self):
        """
        Test make_updates with no results.
        """
        point = self.load('sysperf_points_no_results.json')
        self._test(point)

    def test_single_result(self):
        """
        Test make_updates with single result.
        """

        point = self.load('sysperf_points_small.json')
        self._test(point)

    def test_multiple_results(self):
        """
        Test make_updates with multiple results.
        """

        point = self.load('sysperf_points_multiple_results.json')
        self._test(point)


class TestRedactURL(unittest.TestCase):
    """
    Test suite for redact_url.
    """

    def test_no_password(self):
        """
        Test redact url with no password.
        """
        self.assertEquals('mongodb+srv://localhost/perf',
                          etl_helpers.redact_url('mongodb+srv://localhost/perf'))

    def test_password(self):
        """
        Test redact url with password.
        """
        self.assertEquals('mongodb+srv://user:???@localhost/perf',
                          etl_helpers.redact_url('mongodb+srv://user:password@localhost/perf'))


class TestCreateDescriptor(unittest.TestCase):
    """
    Test suite for create_descriptor.
    """

    def _test_create_descriptor(self, expected, test_identifier, test=None):
        self.assertEqual(etl_helpers.create_descriptor(test_identifier, test=test), expected)

    def test_defaults(self):
        """
        Test create_descriptor defaults.
        """
        self._test_create_descriptor(
            'project_id/variant/task/test/thread_level', {
                'project_id': 'project_id',
                'variant': 'variant',
                'task_name': 'task',
                'test': 'test',
                'thread_level': 'thread_level',
            })

    def test_project(self):
        """
        Test create_descriptor project field.
        """
        self._test_create_descriptor(
            'project/variant/task/test/thread_level', {
                'project': 'project',
                'variant': 'variant',
                'task_name': 'task',
                'test': 'test',
                'thread_level': 'thread_level',
            })

    def test_task(self):
        """
        Test create_descriptor task field.
        """
        self._test_create_descriptor(
            'project/variant/task_name/test/thread_level', {
                'project': 'project',
                'variant': 'variant',
                'task': 'task_name',
                'test': 'test',
                'thread_level': 'thread_level',
            })

    def test_test_param(self):
        """
        Test create_descriptor test param.
        """
        self._test_create_descriptor(
            'project/variant/task_name/TEST/thread_level', {
                'project': 'project',
                'variant': 'variant',
                'task': 'task_name',
                'test': 'test',
                'thread_level': 'thread_level',
            },
            test='TEST')

    def test_no_thread_level(self):
        """
        Test create_descriptor no thread level.
        """
        self._test_create_descriptor('project/variant/task_name/test', {
            'project': 'project',
            'variant': 'variant',
            'task': 'task_name',
            'test': 'test',
        })


class TestFilterNonTestResults(unittest.TestCase):
    def test_empty_results(self):
        self.assertDictEqual({}, etl_helpers._filter_non_test_results({}))

    def test_filters_out_start_end_tasks(self):
        results = {
            'start': 'start',
            'item 1': 'item 1',
            'item 2': 'item 2',
            'end': 'end',
            'item 3': 'item 3'
        }
        filtered = etl_helpers._filter_non_test_results(results)
        self.assertNotIn('start', filtered)
        self.assertNotIn('end', filtered)
        self.assertEqual(3, len(filtered.keys()))

    def test_does_not_filters_out_non_start_end_tasks(self):
        results = {
            'item 1': 'item 1',
            'item 2': 'item 2',
            'item 3': 'item 3'
        }  # yapf: disable
        filtered = etl_helpers._filter_non_test_results(results)
        self.assertDictEqual(results, filtered)


class TestIsValidResults(unittest.TestCase):
    def test_result_with_name_not_in_tests_not_valid(self):
        test_name = 'test_name'
        tests = ['test 0', 'test 2']
        test_result = {'name': test_name}

        self.assertFalse(etl_helpers._is_valid_result(test_result, tests))

    def test_result_with_name_in_tests_is_valid(self):
        test_name = 'test_name'
        tests = ['test 0', test_name, 'test 2']
        test_result = {
            'name': test_name,
            'results': {
                'start': 'start',
                '1': {
                    'ops_per_sec': 100,
                }
            }
        }

        self.assertTrue(etl_helpers._is_valid_result(test_result, tests))

    def test_result_with_no_tests_is_valid(self):
        test_name = 'test_name'
        tests = None
        test_result = {
            'name': test_name,
            'start': 'start',
            'results': {
                '1': {
                    'ops_per_sec': 100,
                }
            }
        }

        self.assertTrue(etl_helpers._is_valid_result(test_result, tests))

    def test_result_with_no_start_is_invalid(self):
        test_name = 'test_name'
        tests = None
        test_result = {
            'name': test_name,
            'results': {
                '1': {
                    'ops_per_sec': 100,
                }
            }
        }  # yapf: disable

        self.assertFalse(etl_helpers._is_valid_result(test_result, tests))

    def test_result_with_no_ops_per_sec_is_invalid(self):
        test_name = 'test_name'
        tests = None
        test_result = {
            'name': test_name,
            'results': {
                '1': {
                    'ops_per_sec': 100,
                },
                '8': {
                    # Does not contain ops_per_sec.
                }
            }
        }

        self.assertFalse(etl_helpers._is_valid_result(test_result, tests))
