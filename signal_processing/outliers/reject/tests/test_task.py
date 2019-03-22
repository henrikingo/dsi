"""
Unit tests for signal_processing/outliers/config.py.
"""
# pylint: disable=missing-docstring
from __future__ import print_function

import os
import unittest

import pymongo
from mock import MagicMock, patch, PropertyMock

from signal_processing.outliers.reject.task import TestAutoRejector, TaskAutoRejector
from test_lib.fixture_files import FixtureFiles

NS = 'signal_processing.outliers.reject.task'
FIXTURE_FILES = FixtureFiles(os.path.dirname(__file__))


def ns(relative_name):  # pylint: disable=invalid-name
    """Return a full name from a name relative to the tested module's name space."""
    return NS + '.' + relative_name


def test_identifier(test='test_name', thread_level='1'):
    return {'test': test, 'thread_level': thread_level}


def create_test_rejector(test='test_name',
                         thread_level='1',
                         task=None,
                         size=15,
                         rejected=[],
                         max_consecutive_rejections=3,
                         minimum_points=15,
                         gesd_result=None,
                         orders=None,
                         adjusted_indexes=None,
                         last_order=None):
    full_series = dict(
        test_identifier=test_identifier(test, thread_level),
        size=size,
        rejected=rejected,
        orders=orders)
    mock_result = MagicMock(
        name='result',
        full_series=full_series,
        gesd_result=gesd_result,
        adjusted_indexes=adjusted_indexes)
    if task is None:
        task = MagicMock(name='task', order=last_order)
    return (TestAutoRejector(mock_result, task, max_consecutive_rejections, minimum_points),
            mock_result, task)


def create_task_rejector(results=[],
                         project='project',
                         variant='variant',
                         task='task',
                         order=0,
                         mongo_uri='',
                         patch=False,
                         status={},
                         max_consecutive_rejections=3,
                         minimum_points=15):
    return TaskAutoRejector(results, project, variant, task, order, mongo_uri, patch, status,
                            max_consecutive_rejections, minimum_points)


class TestTestAutoRejector(unittest.TestCase):
    """Tests for TestAutoRejector."""

    def setUp(self):
        self.subject, _, _ = create_test_rejector()

    def test_ctor(self):
        self.assertEquals(self.subject.test_identifier, test_identifier())
        self.assertEquals(self.subject.test, 'test_name')
        self.assertEquals(self.subject.thread_level, '1')

    def test_full_series(self):
        self.assertDictContainsSubset({
            'test_identifier': test_identifier()
        }, self.subject.full_series)


class TestCanary(unittest.TestCase):
    """Tests for TestAutoRejector."""

    def _test(self, *names):
        task = create_task_rejector()
        rejectors = [create_test_rejector(test=test_name, task=task)[0] for test_name in names]
        return [rejector.canary for rejector in rejectors]

    def test_not_canary(self):
        canaries = self._test('test_name', 'distinct_types_no_predicate-useAgg',
                              'InsertRemove.Genny.Setup', 'NetworkBandwidthx')  # note the x
        self.assertFalse(all(canaries))

    def test_canary(self):
        canaries = self._test('canary_server-cpuloop-10x', 'fio_streaming_bandwidth_test_read_iops',
                              'NetworkBandwidth')
        self.assertTrue(all(canaries))


class TestHasMinimumPoints(unittest.TestCase):
    """Tests for has_minimum_points."""

    def _test(self, *sizes):
        rejectors = [create_test_rejector(size=size)[0] for size in sizes]
        return [rejector.has_minimum_points for rejector in rejectors]

    def test_too_little(self):
        minimum_points = self._test(*range(0, 15))
        self.assertFalse(all(minimum_points))

    def test_enough(self):
        minimum_points = self._test(15, 16)
        self.assertTrue(all(minimum_points))


class TestTooManyRejections(unittest.TestCase):
    """Tests for too_many_rejections."""

    def _test(self, *rejected):
        rejector = create_test_rejector(rejected=rejected)[0]
        return rejector.too_many_rejections

    def test_empty(self):
        too_many = self._test()
        self.assertFalse(too_many)

    def test_single(self):
        too_many = self._test(True)
        self.assertFalse(too_many)

    def test_double(self):
        too_many = self._test(True, True)
        self.assertFalse(too_many)

    def test_triple(self):
        too_many = self._test(True, True, True)
        self.assertTrue(too_many)

    def test_break(self):
        too_many = self._test(True, False, True, True)
        self.assertFalse(too_many)

    def test_all_false(self):
        too_many = self._test(*[False] * 100)
        self.assertFalse(too_many)


class TestMuted(unittest.TestCase):
    """Tests for muted."""

    def _test(self, mutes=False, expired=True):
        mock_mute = MagicMock(name='mute')
        mutes_collection = MagicMock(name='mute_outliers')
        rejector, _, mock_task = create_test_rejector()
        mock_task.model.db.__getitem__.return_value = mutes_collection

        if mutes:
            iterator = iter([mock_mute])
        else:
            iterator = iter([])

        mutes_collection.find.return_value.sort.return_value.limit.return_value = iterator

        with patch(ns('mute_expired')) as mock_mute_expired:
            if not mutes:
                self.assertFalse(rejector.muted)
                mock_mute_expired.assert_not_called()
            else:
                mock_mute_expired.return_value = expired
                self.assertEquals(not expired, rejector.muted)
                mock_mute_expired.assert_called_once_with(mock_mute, mock_task.model.db.points)

        mock_find = mutes_collection.find
        mock_find.assert_called_once_with(test_identifier())

        mock_sort = mock_find.return_value.sort
        mock_sort.assert_called_once_with('order', pymongo.DESCENDING)

        mock_limit = mock_sort.return_value.limit
        mock_limit.assert_called_once_with(1)

    def test_no_mutes(self):
        self._test()

    def test_expired_mutes(self):
        self._test(mutes=True, expired=True)

    def test_active_mute(self):
        self._test(mutes=True, expired=False)


class TestOutlierOrders(unittest.TestCase):
    """Tests for outlier_orders."""

    def test_no_outliers(self):
        mock_gesd_result = MagicMock(name='gesd_result', count=0)
        rejector, mock_result, mock_task = create_test_rejector(gesd_result=mock_gesd_result)

        self.assertListEqual([], rejector.outlier_orders)

    def test_outliers(self):
        orders = ['one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten']
        count = 5
        adjusted_indexes = list(range(count))
        mock_gesd_result = MagicMock(name='gesd_result', count=count)
        rejector, mock_result, mock_task = create_test_rejector(
            gesd_result=mock_gesd_result, orders=orders, adjusted_indexes=adjusted_indexes)

        self.assertListEqual(orders[:count], rejector.outlier_orders)

    def test_offset_outliers(self):
        orders = ['one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten']
        count = 5
        start = count
        adjusted_indexes = list(range(start, len(orders)))
        mock_gesd_result = MagicMock(name='gesd_result', count=count)
        rejector, mock_result, mock_task = create_test_rejector(
            gesd_result=mock_gesd_result, orders=orders, adjusted_indexes=adjusted_indexes)

        self.assertListEqual(orders[count:], rejector.outlier_orders)

    def test_stepped_outliers(self):
        orders = ['one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten']
        count = 5
        adjusted_indexes = list(range(0, len(orders), 2))
        mock_gesd_result = MagicMock(name='gesd_result', count=count)
        rejector, mock_result, mock_task = create_test_rejector(
            gesd_result=mock_gesd_result, orders=orders, adjusted_indexes=adjusted_indexes)

        self.assertListEqual(orders[::2], rejector.outlier_orders)


def create_task_rejector(results=[],
                         project='project',
                         variant='variant',
                         task='task',
                         order=0,
                         mongo_uri='mongo_uri',
                         patch=False,
                         status=None):
    if not status:
        status = {'failures': 0}
    return TaskAutoRejector(results, project, variant, task, order, mongo_uri, patch, status)


class TestTaskAutoRejector(unittest.TestCase):
    """Tests for TaskAutoRejector."""

    def setUp(self):
        self.subject = create_task_rejector()

    def test_ctor(self):
        self.assertListEqual([], self.subject.results)
        self.assertEquals(3, self.subject.max_consecutive_rejections)
        self.assertEquals(15, self.subject.minimum_points)
        self.assertEquals('project', self.subject.project)
        self.assertEquals('variant', self.subject.variant)
        self.assertEquals('task', self.subject.task)
        self.assertEquals(0, self.subject.order)
        self.assertEquals('mongo_uri', self.subject.mongo_uri)
        self.assertEquals({'failures': 0}, self.subject.status)

    def test_model(self):
        with patch(ns('PointsModel')) as mock_clazz:
            mock_model = MagicMock(name='mock model')
            mock_clazz.return_value = mock_model
            self.assertEquals(mock_model, self.subject.model)
            mock_clazz.assert_called_once_with('mongo_uri')


def load_status(filename):
    """
    Load the report.json content from the 'status' field.
    The 'task_id' field allows you to track back to the dsi data.
    Although note: some of these files were edited.
    :param str filename: The json file with the report.json status data.
    :return: A dict of the report.json status data.
    """
    status = FIXTURE_FILES.load_json_file(filename)
    return status['status']


class TestCorrect(unittest.TestCase):
    """Tests for correct."""

    def test_success(self):
        status = load_status('status/success.json')

        subject = create_task_rejector(status=status)
        self.assertTrue(subject.correct)

    def test_fails(self):
        """ test with test failures only"""
        status = load_status('status/fails.json')
        subject = create_task_rejector(status=status)
        self.assertTrue(subject.correct)

    def test_canary(self):
        """ test with test failures only"""
        status = load_status('status/canary.json')
        subject = create_task_rejector(status=status)
        self.assertTrue(subject.correct)

    def test_network(self):
        """ test with test failures only"""
        status = load_status('status/network.json')
        subject = create_task_rejector(status=status)
        self.assertTrue(subject.correct)

    def test_resource(self):
        """ test with test failures only"""
        status = load_status('status/resource_sanity_checks.json')
        subject = create_task_rejector(status=status)
        self.assertTrue(subject.correct)

    def test_core(self):
        """ test with test failures only"""
        status = load_status('status/core.json')
        subject = create_task_rejector(status=status)
        self.assertFalse(subject.correct)

    def test_db_hash(self):
        """ test with test failures only"""
        status = load_status('status/db-hash.json')
        subject = create_task_rejector(status=status)
        self.assertFalse(subject.correct)

    def test_fio(self):
        """ test with test failures only"""
        status = load_status('status/core.json')
        subject = create_task_rejector(status=status)
        self.assertFalse(subject.correct)

    def test_validate(self):
        """ test with test failures only"""
        status = load_status('status/validate.json')
        subject = create_task_rejector(status=status)
        self.assertFalse(subject.correct)

    def test_multiple(self):
        """ test with test failures only"""
        status = load_status('status/multiple.json')
        subject = create_task_rejector(status=status)
        self.assertFalse(subject.correct)


class TestRejects(unittest.TestCase):
    """Tests for rejects."""

    def test_no_results(self):
        results = []
        subject = create_task_rejector(results=results)
        self.assertListEqual([], subject.rejects)

    def test_not_latest(self):
        order = 100
        num_orders = 200
        orders = list(range(num_orders))
        full_series = dict(orders=orders, test_identifier=test_identifier())
        result = MagicMock(name='result', full_series=full_series)
        results = [result]

        subject = create_task_rejector(results=results, order=order)
        self.assertListEqual([], subject.rejects)

    def test_latest_but_no_outliers(self):
        order = 200
        orders = 200
        full_series = dict(orders=list(range(orders)), test_identifier=test_identifier())
        result = MagicMock(name='result', full_series=full_series)
        results = [result]
        subject = create_task_rejector(results=results, order=order)
        self.assertListEqual([], subject.rejects)

    def test_latest_and_not_outliers(self):
        order = 200
        orders = 200
        full_series = dict(orders=list(range(orders)), test_identifier=test_identifier())
        result = MagicMock(name='result', full_series=full_series)
        results = [result]
        subject = create_task_rejector(results=results, order=order)
        subject.results[0]._outlier_orders = range(100)
        self.assertListEqual([], subject.rejects)

    def test_latest_and_outliers(self):
        order = 200
        orders = 200
        full_series = dict(orders=list(range(orders)), test_identifier=test_identifier())
        result = MagicMock(name='result1', full_series=full_series)
        results = [result]
        subject = create_task_rejector(results=results, order=order)
        subject.results[0]._outlier_orders = range(100) + [order]
        self.assertEqual(1, len(subject.rejects))

    def test_multiple(self):
        order = 200
        orders = 200
        result1 = MagicMock(
            name='result1',
            full_series=dict(
                orders=list(range(orders)), test_identifier=test_identifier(test='first')))
        result2 = MagicMock(
            name='result2',
            full_series=dict(
                orders=list(range(orders)), test_identifier=test_identifier(test='second')))
        results = [result1, result2]
        subject = create_task_rejector(results=results, order=order)
        subject.results[0]._outlier_orders = range(100) + [order]
        subject.results[1]._outlier_orders = range(100)
        self.assertEqual(1, len(subject.rejects))
        self.assertEqual(subject.rejects[0].test_identifier['test'], 'first')


class TestFilteredRejects(unittest.TestCase):
    """Tests for filtered_rejects."""

    def test_no_results(self):
        results = []
        subject = create_task_rejector(results=results)
        self.assertListEqual([], subject.filtered_rejects())

    def test_not_latest(self):
        order = 100
        num_orders = 200
        orders = list(range(num_orders))
        full_series = dict(orders=orders, test_identifier=test_identifier())
        result = MagicMock(name='result', full_series=full_series)
        results = [result]

        subject = create_task_rejector(results=results, order=order)
        self.assertListEqual([], subject.filtered_rejects())

    def test_latest_but_no_outliers(self):
        order = 200
        orders = 200
        full_series = dict(orders=list(range(orders)), test_identifier=test_identifier())
        result = MagicMock(name='result', full_series=full_series)
        results = [result]
        subject = create_task_rejector(results=results, order=order)
        self.assertListEqual([], subject.filtered_rejects())

    def test_latest_and_not_outliers(self):
        order = 200
        orders = 200
        full_series = dict(orders=list(range(orders)), test_identifier=test_identifier())
        result = MagicMock(name='result', full_series=full_series)
        results = [result]
        subject = create_task_rejector(results=results, order=order)
        subject.results[0]._outlier_orders = range(100)
        self.assertListEqual([], subject.filtered_rejects())

    def test_latest_and_outliers(self):
        order = 200
        orders = 200
        full_series = dict(
            orders=list(range(orders)),
            size=orders,
            rejected=[None] * orders,
            test_identifier=test_identifier(test='canary_client-cpuloop-10x'))
        result = MagicMock(name='result1', full_series=full_series)
        results = [result]
        subject = create_task_rejector(results=results, order=order)
        subject.results[0]._outlier_orders = range(100) + [order]

        mock_model = MagicMock(name='model')
        mock_collection = MagicMock(name='collection')
        mock_model.db.__getitem__.return_value = mock_collection
        mock_mute = MagicMock(name='mute')
        mock_collection.find.return_value.sort.return_value.limit.return_value = iter([mock_mute])
        subject._model = mock_model

        with patch(ns('mute_expired')) as mock_mute_expired:
            mock_mute_expired.return_value = True
            self.assertEqual(1, len(subject.filtered_rejects()))

    def test_multiple(self):
        order = 200
        orders = 200
        result1 = MagicMock(
            name='result1',
            full_series=dict(
                orders=list(range(orders)),
                size=orders,
                rejected=[None] * orders,
                test_identifier=test_identifier(test='canary_client-cpuloop-10x')))
        result2 = MagicMock(
            name='result2',
            full_series=dict(
                orders=list(range(orders)),
                size=orders,
                rejected=[None] * orders,
                test_identifier=test_identifier(test='distinct_types_no_predicate-useAgg')))
        results = [result1, result2]
        subject = create_task_rejector(results=results, order=order)
        subject.results[0]._outlier_orders = range(100) + [order]
        subject.results[1]._outlier_orders = range(100)

        mock_model = MagicMock(name='model')
        mock_collection = MagicMock(name='collection')
        mock_model.db.__getitem__.return_value = mock_collection
        mock_mute = MagicMock(name='mute')
        mock_collection.find.return_value.sort.return_value.limit.return_value = iter([mock_mute])
        subject._model = mock_model

        with patch(ns('mute_expired')) as mock_mute_expired:
            mock_mute_expired.return_value = True
            self.assertEqual(1, len(subject.filtered_rejects()))
        self.assertEqual(subject.filtered_rejects()[0].test_identifier['test'],
                         'canary_client-cpuloop-10x')

    def test_multiple_order(self):
        order = 200
        orders = 200
        result1 = MagicMock(
            name='result1',
            full_series=dict(
                orders=list(range(orders)),
                size=orders,
                rejected=[None] * orders,
                test_identifier=test_identifier(test='distinct_types_no_predicate-useAgg')))
        result2 = MagicMock(
            name='result2',
            full_series=dict(
                orders=list(range(orders)),
                size=orders,
                rejected=[None] * orders,
                test_identifier=test_identifier(test='canary_client-cpuloop-10x')))
        results = [result1, result2]
        subject = create_task_rejector(results=results, order=order)
        subject.results[0]._outlier_orders = range(100) + [order]
        subject.results[1]._outlier_orders = range(100) + [order]

        mock_model = MagicMock(name='model')
        mock_collection = MagicMock(name='collection')
        mock_model.db.__getitem__.return_value = mock_collection
        mock_mute = MagicMock(name='mute')
        mock_collection.find.return_value.sort.return_value.limit.return_value = iter([mock_mute])
        subject._model = mock_model

        with patch(ns('mute_expired')) as mock_mute_expired:
            mock_mute_expired.return_value = True
            self.assertEqual(1, len(subject.filtered_rejects()))
        self.assertEqual(subject.filtered_rejects()[0].test_identifier['test'],
                         'canary_client-cpuloop-10x')


class TestReject(unittest.TestCase):
    """Tests for reject."""

    def create_subject(self, last_order=100, orders_range=None, test='canary_server-sleep-10ms'):
        if orders_range is None:
            orders_range = last_order + 1
        subject, _, _ = create_test_rejector(
            test=test, last_order=last_order, orders=range(orders_range))
        return subject

    def _test(self,
              canary=True,
              muted=False,
              too_many_rejections=False,
              has_minimum_points=True,
              latest=True):
        with patch(ns('TestAutoRejector.canary'), new_callable=PropertyMock) as mock_canary,\
             patch(ns('TestAutoRejector.muted'), new_callable=PropertyMock) as mock_muted,\
             patch(ns('TestAutoRejector.too_many_rejections'), new_callable=PropertyMock)\
                as mock_too_many_rejections,\
             patch(ns('TestAutoRejector.has_minimum_points'), new_callable=PropertyMock)\
                as mock_has_minimum_points,\
             patch(ns('TestAutoRejector.latest'), new_callable=PropertyMock) as mock_latest:
            mock_canary.return_value = canary
            mock_muted.return_value = muted
            mock_too_many_rejections.return_value = too_many_rejections
            mock_has_minimum_points.return_value = has_minimum_points
            mock_latest.return_value = latest
            subject = self.create_subject()
            return subject.reject

    def test_reject(self):
        self.assertTrue(self._test())

    def test_toggle_canary(self):
        self.assertFalse(self._test(canary=False))

    def test_toggle_muted(self):
        self.assertFalse(self._test(muted=True))

    def test_toggle_too_many_rejections(self):
        self.assertFalse(self._test(too_many_rejections=True))

    def test_toggle_has_minimum_points(self):
        self.assertFalse(self._test(has_minimum_points=False))

    def test_toggle_latest(self):
        self.assertFalse(self._test(latest=False))


class TestLatest(unittest.TestCase):
    """Tests for latest."""

    def create_subject(self, last_order=100, orders_range=None):
        if orders_range is None:
            orders_range = last_order + 1
        subject, _, _ = create_test_rejector(last_order=last_order, orders=range(orders_range))
        return subject

    def test_latest_equal(self):
        order = 100
        subject = self.create_subject(last_order=order)
        self.assertTrue(subject.latest)

    def test_latest_gt(self):
        order = 100
        subject = self.create_subject(last_order=order, orders_range=order)
        self.assertTrue(subject.latest)

    def test_latest_lt(self):
        order = 100
        subject = self.create_subject(last_order=order - 1, orders_range=order + 1)
        self.assertFalse(subject.latest)
