"""
Unit tests for signal_processing/detect_changes.py.
"""

import os
import time
import unittest
from collections import OrderedDict, defaultdict

import pymongo
from mock import ANY, MagicMock, call, patch

import signal_processing.detect_changes as detect_changes
from signal_processing.commands import jobs
from signal_processing.detect_changes import main
from test_lib.fixture_files import FixtureFiles
from click.testing import CliRunner

FIXTURE_FILES = FixtureFiles(os.path.dirname(__file__))


def statistics(i):
    """ helper function to create dummy stats:

    :parameter int i: An int, generally the index.
    :return: A stats dict().
    """
    return {'next': i * 10, 'previous': (i * 10) + 1}


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
             patch('signal_processing.detect_changes.PointsModel', autospec=True) as mock_PointsModel:

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


def copy_and_update(x, **kwargs):
    z = x.copy()
    z.update(kwargs)
    return z


class TestGetPoints(unittest.TestCase):
    """
    Test suite for the PointsModel.get_points.
    """

    def setUp(self):
        self.mongo_uri = 'mongodb+srv://fake@dummy-server.mongodb.net/perf'
        self.sysperf_perf_json = FIXTURE_FILES.load_json_file('sysperf_perf.json')
        self.sysperf_points = FIXTURE_FILES.load_json_file('sysperf_points.json')

    def _test_get_points(self, min_points=None, expected=None, order=101):
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
            if '_id' not in expected:
                expected['_id'] = None
            mock_db.points.aggregate.return_value = [expected]
            mock_cursor.return_value = self.sysperf_points
            test_model = detect_changes.PointsModel(self.mongo_uri, min_points=min_points)

            self.assertEqual(expected, test_model.get_points(test_identifier, order))
            calls = mock_db.points.aggregate.call_args_list
            self.assertTrue(len(calls) == 1)

            self.assertTrue(len(calls[0][0][0]) == 5)

            pipeline = calls[0][0][0]
            first = pipeline[0]
            self.assertIn('$match', first)
            match = first['$match']

            if order is not None:
                self.assertIn('order', match)
                self.assertEquals(match['order'], {'$gt': order})
            else:
                self.assertNotIn('order', match)

    def test_get_points(self):
        """ test get points. """
        self._test_get_points()

    def test_get_points_no_order(self):
        """ test get points no order. """
        self._test_get_points(order=None)

    def test_get_points_assertion(self):
        """ test get point asserts invalid sizes. """
        expected = {
            key: range(10) if key != 'create_times' else range(5)
            for key in detect_changes.ARRAY_FIELDS
        }

        with self.assertRaisesRegexp(Exception, 'All array sizes were not equal:'):
            self._test_get_points(expected=expected)

    def test_get_points_custom_min_points(self):
        """
        Test that min_points is called on cursor when specified.
        """
        self._test_get_points(min_points=10)


class TestGetClosestOrderNoChangePoints(unittest.TestCase):
    """
    Test suite for the PointsModel._get_closest_order_no_change_points.
    """

    def setUp(self):
        self.mongo_uri = 'mongodb+srv://fake@dummy-server.mongodb.net/perf'
        self.test_identifier = {'thread_level': '1'}

    def _test_gte_zero_none(self, min_points=None):
        with patch('signal_processing.detect_changes.pymongo.MongoClient') as mock_mongo_client:
            mock_change_points = MagicMock(name='change_points', autospec=True)
            mock_db = MagicMock(name='db', autospec=True, change_points=mock_change_points)

            mock_mongo_client.return_value.get_database.return_value = mock_db
            test_model = detect_changes.PointsModel(self.mongo_uri, min_points=min_points)
            self.assertIsNone(test_model._get_closest_order_no_change_points(self.test_identifier))

    def test_with_min_points_none(self):
        self._test_gte_zero_none()

    def test_with_min_points_0(self):
        self._test_gte_zero_none(min_points=0)

    def test_with_min_points_gt_0(self):
        self._test_gte_zero_none(min_points=12)

    def _test_lt_0(self, min_points=-101, count=0):
        with patch('signal_processing.detect_changes.pymongo.MongoClient') as mock_mongo_client:
            mock_points = MagicMock(name='points', autospec=True)
            mock_db = MagicMock(name='db', autospec=True, points=mock_points)

            mock_mongo_client.return_value.get_database.return_value = mock_db

            mock_points.count.return_value = count

            test_model = detect_changes.PointsModel(self.mongo_uri, min_points=min_points)
            self.assertIsNone(test_model._get_closest_order_no_change_points(self.test_identifier))
            mock_points.count.assert_called_once_with({'results.thread_level': '1'})

    def test_with_min_points_lt_0(self):
        self._test_lt_0()

    def test_with_min_points_lt_0_gt_count(self):
        self._test_lt_0(min_points=-101, count=10)

    def _test_count_gt_min_points(self, min_points=-101, count=200):
        with patch('signal_processing.detect_changes.pymongo.MongoClient') as mock_mongo_client:
            mock_points = MagicMock(name='points', autospec=True)
            mock_db = MagicMock(name='db', autospec=True, points=mock_points)

            mock_mongo_client.return_value.get_database.return_value = mock_db

            mock_points.count.return_value = count
            order = count + 1
            return_value = [{'order': order}]
            mock_points.find.return_value.sort.return_value.skip.return_value.limit.return_value =\
                return_value

            test_model = detect_changes.PointsModel(self.mongo_uri, min_points=min_points)
            self.assertEquals(order,
                              test_model._get_closest_order_no_change_points(self.test_identifier))
            mock_points.count.assert_called_once_with({'results.thread_level': '1'})
            chained = call({'results.thread_level': '1'}, {'order': 1}).\
                sort('order', pymongo.DESCENDING).\
                skip(abs(min_points) - 1).\
                limit(1)
            self.assertEquals(mock_points.find.mock_calls, chained.call_list())

    def test_count_gt_min_points(self):
        self._test_count_gt_min_points()


class TestGetClosestOrderWithChangePoints(unittest.TestCase):
    """
    Test suite for the PointsModel._get_closest_order_for_change_points.
    """

    def setUp(self):
        self.mongo_uri = 'mongodb+srv://fake@dummy-server.mongodb.net/perf'
        boundaries = FIXTURE_FILES.load_json_file('boundaries.json')
        self.buckets = boundaries['buckets']
        self.change_points = boundaries['change_points']

        self.change_point_orders = [change_point['order'] for change_point in self.change_points]

    def _test_change_point(self, min_points=1, expected=14117):
        """ test helper first change point expected. """

        # boundaries = db.change_points.find(cp_query).sort({order: 1}).toArray().map(x= > x.order)

        with patch('signal_processing.detect_changes.pymongo.MongoClient') as mock_mongo_client:
            mock_change_points = MagicMock(name='change_points', autospec=True)
            mock_points = MagicMock(name='points', autospec=True)
            mock_db = MagicMock(
                name='db', autospec=True, points=mock_points, change_points=mock_change_points)

            mock_mongo_client.return_value.get_database.return_value = mock_db

            mock_change_points.find.return_value.sort.return_value = self.change_points
            mock_points.aggregate.return_value = self.buckets

            test_model = detect_changes.PointsModel(self.mongo_uri, min_points=min_points)

            result = test_model._get_closest_order_for_change_points(self.change_point_orders, {
                'thread_level': '1'
            })
            self.assertEquals(expected, result)

            mock_points.aggregate.assert_called_once_with([{
                '$match': {
                    'results.thread_level': '1'
                }
            }, {
                '$bucket': {
                    'groupBy': "$order",
                    'boundaries': ANY,
                    'default': "Other",
                    'output': {
                        'count': {
                            '$sum': 1
                        }
                    }
                }
            }])

    def test_1(self):
        """ Test min_points 1 returns first change point. """
        self._test_change_point()

    def test_lt_first(self):
        """ Test min_points less than first change point returns first. """
        self._test_change_point(min_points=292)

    def test_eq_first(self):
        """ Test min_points less than first change point returns first. """
        self._test_change_point(min_points=293)

    def test_lt_second(self):
        """ Test lt second return first. """
        self._test_change_point(min_points=294, expected=14033)

    def test_lt_last_changepoint(self):
        """ Test get_closest_order at actual last change point. """
        self._test_change_point(min_points=1286, expected=11287)

    def test_eq_last_changepoint(self):
        """ Test get_closest_order at actual last change point. """
        self._test_change_point(min_points=1287, expected=11287)

    def test_gt_last_changepoint(self):
        """ Test get_closest_order at actual last change point. """
        self._test_change_point(min_points=1288, expected=None)

    def test_eq_end(self):
        """ Test at end boundary returns None. """
        self._test_change_point(min_points=1360, expected=None)

    def test_beyond_end(self):
        """ Test beyond end boundary returns None. """
        self._test_change_point(min_points=100000, expected=None)


class TestGetClosestOrder(unittest.TestCase):
    """
    Test suite for the PointsModel.get_closest_order.
    """

    def setUp(self):
        self.mongo_uri = 'mongodb+srv://fake@dummy-server.mongodb.net/perf'
        boundaries = FIXTURE_FILES.load_json_file('boundaries.json')
        self.buckets = boundaries['buckets']
        self.change_points = boundaries['change_points']

        self.change_point_orders = [change_point['order'] for change_point in self.change_points]

    def _test_get_closest_order_min_points_none(self, min_points_is_none=True):
        with patch('signal_processing.detect_changes.pymongo.MongoClient') as mock_mongo_client:
            mock_change_points = MagicMock(name='change_points', autospec=True)
            mock_db = MagicMock(name='db', autospec=True, change_points=mock_change_points)

            mock_mongo_client.return_value.get_database.return_value = mock_db
            min_points = None if min_points_is_none else 0
            test_model = detect_changes.PointsModel(self.mongo_uri, min_points=min_points)
            self.assertIsNone(test_model.get_closest_order({}))
            mock_change_points.find.assert_not_called()

    def test_with_min_points_none(self):
        self._test_get_closest_order_min_points_none()

    def test_with_min_points_0(self):
        self._test_get_closest_order_min_points_none(False)

    def _test_get_closest_order(self, no_change_points=True):
        with patch('signal_processing.detect_changes.pymongo.MongoClient') as mock_mongo_client:
            mock_change_points = MagicMock(name='change_points', autospec=True)
            mock_points = MagicMock(name='points', autospec=True)
            mock_db = MagicMock(
                name='db', autospec=True, points=mock_points, change_points=mock_change_points)

            mock_mongo_client.return_value.get_database.return_value = mock_db

            mock_points.count.return_value = 0

            if no_change_points:
                mock_change_points.find.return_value.sort.return_value = []
            else:
                mock_change_points.find.return_value.sort.return_value = self.change_points

            min_points = 101
            test_model = detect_changes.PointsModel(self.mongo_uri, min_points=min_points)
            mock_change_points = MagicMock(name='_get_closest_order_for_change_points')
            mock_change_points.return_value = '_get_closest_order_for_change_points'
            test_model._get_closest_order_for_change_points = mock_change_points

            mock_no_change_points = MagicMock(name='_get_closest_order_no_change_points')
            test_model._get_closest_order_no_change_points = mock_no_change_points
            mock_no_change_points.return_value = '_get_closest_order_no_change_points'

            if no_change_points:
                expected = '_get_closest_order_no_change_points'
            else:
                expected = '_get_closest_order_for_change_points'
            test_identifier = {'thread_level': '1'}
            self.assertEquals(expected, test_model.get_closest_order(test_identifier))

            if no_change_points:
                mock_change_points.assert_not_called()
                mock_no_change_points.assert_called_once_with(test_identifier)
            else:
                mock_change_points.assert_called_once_with(self.change_point_orders,
                                                           test_identifier)
                mock_no_change_points.assert_not_called()

    def test_with_no_change_points(self):
        self._test_get_closest_order()

    def test_with_change_points(self):
        self._test_get_closest_order(True)


class TestFindPreviousChangePoint(unittest.TestCase):
    def setUp(self):
        self.mongo_uri = 'mongodb+srv://fake@dummy-server.mongodb.net/perf'

    def _test(self, previous=None):
        if previous is None:
            previous = []
        mock_db = MagicMock(name='db', autospec=True)

        with patch('signal_processing.detect_changes.pymongo.MongoClient') as mock_mongo_client:
            mock_mongo_client.return_value.get_database.return_value = mock_db
            test_model = detect_changes.PointsModel(self.mongo_uri)
            mock_db.change_points.find.return_value.sort.return_value.limit.return_value = previous

            return_value = test_model._find_previous_change_point({
                'test': 'identifier'
            }, {
                'order': 'current'
            })

            chained = call({'test': 'identifier', 'order': {'$lt': 'current'}}).\
                sort('order', pymongo.DESCENDING).\
                limit(1)
            self.assertEquals(mock_db.change_points.find.mock_calls, chained.call_list())
            return return_value

    def test_no_previous(self):
        """ test no previous """
        self.assertIsNone(self._test())

    def test_previous(self):
        """ test with previous"""
        self.assertEquals('previous', self._test(previous=['previous']))


class TestUpdatePreviousChangePoint(unittest.TestCase):
    """
    Test suite for the PointsModel.update_previous_change_point class.
    """

    def setUp(self):
        self.mongo_uri = 'mongodb+srv://fake@dummy-server.mongodb.net/perf'

    def _test(self, has_previous=False):
        mock_db = MagicMock(name='db', autospec=True)

        with patch('signal_processing.detect_changes.pymongo.MongoClient') as mock_mongo_client:
            mock_mongo_client.return_value.get_database.return_value = mock_db
            test_model = detect_changes.PointsModel(self.mongo_uri)
            test_model._find_previous_change_point = MagicMock(name='_find_previous_change_point')
            previous = None
            if has_previous:
                previous = {'order': 'previous'}
            test_model._find_previous_change_point.return_value = previous

            test_identifier = {'test': 'identifier'}
            change_point = {'order': 'current', 'statistics': statistics(0)}

            test_model.update_previous_change_point(test_identifier, change_point)

            test_model._find_previous_change_point.assert_called_once_with(
                test_identifier, change_point)
            if previous:
                query = test_identifier.copy()
                query['order'] = previous['order']

                # next of previous is previous of current
                update = {'$set': {'statistics.next': change_point['statistics']['previous']}}
                mock_db.change_points.update_one.assert_called_once_with(query, update)

    def test_no_previous(self):
        """ test no previous """
        self._test()

    def test_previous(self):
        """ test with previous"""
        self._test(has_previous=True)


class TestComputeChangePoints(unittest.TestCase):
    """
    Test suite for the PointsModel.compute_change_points class.
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

    def _test_compute_change_points(self,
                                    exception=False,
                                    order=None,
                                    old_change_points=True,
                                    reverse=False):
        # pylint: disable=too-many-locals, too-many-branches

        with patch('pymongo.InsertOne') as mock_insert, \
                patch('pymongo.DeleteMany') as mock_delete, \
                patch('signal_processing.change_points.detection.detect_change_points', autospec=True) as mock_detect, \
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
                        ('version_id', 'version {}'.format(i)),
                        ('statistics', statistics(i))
                    ]) for i in range(1, 3)]  # yapf: disable

            mock_insert.side_effect = ["InsertOne 1", "InsertOne 2"]
            mock_bulk = MagicMock(name='bulk', autospec=True, bulk_api_result='bulk_api_result')
            mock_mongo_client.return_value.get_database.return_value = mock_db
            mock_db.change_points.bulk_write.return_value = mock_bulk

            size = 3
            values = range(1, size + 1)
            thread_level_results = {
                '_id': None,
                'thread_level': thread_level,
                'size': size,
                'series': values,
                'revisions': ['revision {}'.format(i) for i in values],
                'orders': values,
                'create_times': values,
                'task_ids': ['task {}'.format(i) for i in values],
                'version_ids': ['version {}'.format(i) for i in values],
            }

            if old_change_points:
                change_points = [{'order': i, 'statistics': statistics(i)} for i in range(1, 3)]
            else:
                change_points = []

            mock_db.points.aggregate.return_value = [thread_level_results]
            mock_db.points.count.return_value = 100
            mock_detect.return_value = list(reversed(change_points)) if reverse else change_points

            test_identifier = {
                'project': self.sysperf_perf_json['project_id'],
                'variant': self.sysperf_perf_json['variant'],
                'task': self.sysperf_perf_json['task_name'],
                'test': self.sysperf_perf_json['data']['results'][0]['name'],
                'thread_level': thread_level
            }

            test_model = detect_changes.PointsModel(self.mongo_uri)
            test_model.get_closest_order = MagicMock(name='get_closest_order')
            test_model.get_closest_order.return_value = order

            if order is None:
                query = test_identifier
            else:
                query = test_identifier.copy()
                query['order'] = {'$gt': order}

            test_model.update_previous_change_point = MagicMock(name='update_previous_change_point')

            if exception:
                with self.assertRaises(Exception) as context:
                    test_model.compute_change_points(test_identifier, weighting=0.001)
                self.assertTrue('boom' in context.exception)

                # delete is called twice in this case
                delete_calls = [call(query), call(query)]
            else:
                actual_size, num_change_points = test_model.compute_change_points(
                    test_identifier, weighting=0.001)

                self.assertEqual(actual_size, size)
                self.assertEqual(num_change_points, 2 if old_change_points else 0)

                delete_calls = [call(query)]

                if old_change_points:
                    test_model.update_previous_change_point.assert_called_once_with(
                        test_identifier, change_points[0])
                else:
                    test_model.update_previous_change_point.assert_not_called()

            # delete is called once or twice
            mock_delete.assert_has_calls(delete_calls)

            test_model.get_closest_order.assert_called_once_with(test_identifier)
            mock_db.change_points.find.assert_called_once_with(query)
            if old_change_points:
                mock_insert.assert_has_calls(
                    [call(expected_insert) for expected_insert in expected_inserts])
            else:
                mock_insert.assert_not_called()

            mock_mongo_client.return_value.get_database.assert_called_once_with()
            mock_mongo_client.assert_called_once_with(self.mongo_uri)

            expected_bulk_writes = ["DeleteMany"]
            if old_change_points:
                expected_bulk_writes.extend(["InsertOne 1", "InsertOne 2"])
            mock_db.change_points.bulk_write.assert_called_once_with(expected_bulk_writes)
            mock_detect.assert_called_once_with(
                thread_level_results,
                pvalue=None,
                github_credentials=None,
                mongo_repo=None,
                weighting=0.001)

    def test_compute_change_points(self):
        """ test compute change points no order. """
        self._test_compute_change_points()

    def test_compute_change_points_with_order(self):
        """ test compute change points with order. """
        self._test_compute_change_points(order=101)

    def test_compute_change_points_reversed_order(self):
        """ test compute change points reversed order. """
        self._test_compute_change_points(reverse=True)

    def test_compute_change_points_rollback(self):
        self._test_compute_change_points(True)

    def test_compute_no_change_points(self):
        self._test_compute_change_points(old_change_points=False)

    def _test_detect_changes(self, mock_evg_client, mock_etl_helpers, mock_driver, is_patch=False):
        """
        test_detect_changes helper.
        """
        mock_runner = mock_driver.return_value
        min_points = None
        detect_changes.detect_changes('task_id', is_patch, 'mongo_uri', min_points, 1)
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
            'tid', 'patch', 'muri', 500, None, mongo_repo='../src', progressbar=False)

    @patch('signal_processing.detect_changes.detect_changes')
    @patch('signal_processing.detect_changes.config.ConfigDict', autospec=True)
    @patch('signal_processing.detect_changes.log.setup_logging')
    def test_exception(self, mock_logging, mock_config_dict, mock_detect_changes):
        """
        Test main handles errors.

        """
        mock_detect_changes.return_value = (jobs.Job(time.sleep), )
        result = self.runner.invoke(main)
        self.assertEqual(result.exit_code, 2)
        self.assertIn('1 Unexpected Exceptions', result.output)
