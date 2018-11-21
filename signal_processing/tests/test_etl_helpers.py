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
    @patch('signal_processing.etl_helpers.pymongo.MongoClient', autospec=True)
    def test_load(self, mock_MongoClient):
        """
        Test that load works with a standard configuration.
        """
        self.sysperf_perf_json = FIXTURE_FILES.load_json_file('sysperf_perf_small.json')
        self.sysperf_points = FIXTURE_FILES.load_json_file('sysperf_points_small.json')
        mock_db = MagicMock(name='db', autospec=True)
        mock_MongoClient.return_value.get_database.return_value = mock_db
        etl_helpers.load(self.sysperf_perf_json, self.mongo_uri)
        mock_MongoClient.assert_called_once_with(self.mongo_uri)
        mock_MongoClient.return_value.get_database.assert_called_once_with()
        mock_db.points.bulk_write.assert_called_once_with(
            [
                pymongo.UpdateOne(
                    {
                        'task': u'mixed_workloads_WT',
                        'variant': u'wtdevelop-1-node-replSet',
                        'version_id': u'sys_perf_e31a40ab59fb5c784ff8d15f07c0b811bd54a516',
                        'project': u'sys-perf',
                        'test': u'mixed_findOne',
                        'revision': u'e31a40ab59fb5c784ff8d15f07c0b811bd54a516'
                    }, {"$set": self.sysperf_points[0]},
                    upsert=True)
            ],
            ordered=False)

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

    @patch('signal_processing.etl_helpers.pymongo.MongoClient', autospec=True)
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
                        ), )
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
