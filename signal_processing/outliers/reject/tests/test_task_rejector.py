"""
Unit tests for signal_processing/outliers/task.py.
"""
from __future__ import print_function

import re
import unittest

import bson
from mock import MagicMock, patch

from signal_processing.model.configuration import DEFAULT_CONFIG, OutlierConfiguration
from signal_processing.outliers.reject.tests.helper import create_task_rejector, load_status, \
    test_identifier

NS = 'signal_processing.outliers.reject.task'


def ns(relative_name):  # pylint: disable=invalid-name
    """Return a full name from a name relative to the tested module's name space."""
    return NS + '.' + relative_name


class TestTaskAutoRejector(unittest.TestCase):
    """Tests for TaskAutoRejector."""

    def setUp(self):
        self.subject = create_task_rejector()

    def test_ctor(self):
        self.assertListEqual([], self.subject.results)
        self.assertEquals('project', self.subject.project)
        self.assertEquals('variant', self.subject.variant)
        self.assertEquals('task', self.subject.task)
        self.assertEquals(0, self.subject.order)
        self.assertEquals('mongo_uri', self.subject.mongo_uri)
        self.assertEquals({'failures': 0}, self.subject.status)

    def test_points_model(self):
        with patch(ns('PointsModel')) as mock_clazz:
            mock_model = MagicMock(name='mock model')
            mock_clazz.return_value = mock_model
            self.assertEquals(mock_model, self.subject.points_model)
            mock_clazz.assert_called_once_with('mongo_uri')

    def test_configuration_model(self):
        with patch(ns('ConfigurationModel')) as mock_clazz:
            mock_model = MagicMock(name='mock model')
            mock_clazz.return_value = mock_model
            self.assertEquals(mock_model, self.subject.configuration_model)
            mock_clazz.assert_called_once_with('mongo_uri')

    def test_config(self):
        with patch(ns('combine_outlier_configs')) as mock_combine_outlier_configs:
            mock_configuration_model = MagicMock(name='configuration model')
            self.subject._configuration_model = mock_configuration_model
            self.subject._config = None

            mock_config = mock_combine_outlier_configs.return_value
            self.assertEquals(mock_config, self.subject.config)
            self.assertEquals(mock_config, self.subject.config)

            mock_configuration_model.get_configuration.assert_called_once_with(
                self.subject.task_identifier)
            mock_combine_outlier_configs.assert_called_once_with(
                self.subject.task_identifier,
                mock_configuration_model.get_configuration.return_value,
                self.subject.override_config)


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
        subject._config = DEFAULT_CONFIG
        self.assertTrue(subject.correct)

    def test_canary(self):
        """ test with test failures only"""
        status = load_status('status/canary.json')
        subject = create_task_rejector(status=status)
        subject._config = DEFAULT_CONFIG
        self.assertTrue(subject.correct)

    def test_network(self):
        """ test with test failures only"""
        status = load_status('status/network.json')
        subject = create_task_rejector(status=status)
        subject._config = DEFAULT_CONFIG
        self.assertTrue(subject.correct)

    def test_resource(self):
        """ test with test failures only"""
        status = load_status('status/resource_sanity_checks.json')
        subject = create_task_rejector(status=status)
        subject._config = DEFAULT_CONFIG
        self.assertTrue(subject.correct)

    def test_core(self):
        """ test with test failures only"""
        status = load_status('status/core.json')
        subject = create_task_rejector(status=status)
        subject._config = DEFAULT_CONFIG
        self.assertFalse(subject.correct)

    def test_db_hash(self):
        """ test with test failures only"""
        status = load_status('status/db-hash.json')
        subject = create_task_rejector(status=status)
        subject._config = DEFAULT_CONFIG
        self.assertFalse(subject.correct)

    def test_fio(self):
        """ test with test failures only"""
        status = load_status('status/core.json')
        subject = create_task_rejector(status=status)
        subject._config = DEFAULT_CONFIG
        self.assertFalse(subject.correct)

    def test_validate(self):
        """ test with test failures only"""
        status = load_status('status/validate.json')
        subject = create_task_rejector(status=status)
        subject._config = DEFAULT_CONFIG
        self.assertFalse(subject.correct)

    def test_multiple(self):
        """ test with test failures only"""
        status = load_status('status/multiple.json')
        subject = create_task_rejector(status=status)
        subject._config = DEFAULT_CONFIG
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
        subject._points_model = mock_model

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
        subject._points_model = mock_model

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
        subject._points_model = mock_model

        with patch(ns('mute_expired')) as mock_mute_expired:
            mock_mute_expired.return_value = True
            self.assertEqual(1, len(subject.filtered_rejects()))
        self.assertEqual(subject.filtered_rejects()[0].test_identifier['test'],
                         'canary_client-cpuloop-10x')


class TestCanaryPattern(unittest.TestCase):
    """Tests for canary_pattern."""

    def test_re(self):
        canary_pattern = re.compile('pattern')
        config = OutlierConfiguration(canary_pattern=canary_pattern)
        subject = create_task_rejector(config=config)

        self.assertEquals(canary_pattern, subject.canary_pattern)

    def test_bson_regex(self):
        pattern = 'pattern'
        flags = re.IGNORECASE
        canary_pattern = bson.Regex(pattern, flags=flags)
        config = OutlierConfiguration(canary_pattern=canary_pattern)
        subject = create_task_rejector(config=config)

        self.assertNotEquals(canary_pattern, subject.canary_pattern)
        self.assertEquals(pattern, subject.canary_pattern.pattern)
        self.assertEquals(flags, subject.canary_pattern.flags)


class TestCanaryPattern(unittest.TestCase):
    """Tests for canary_pattern."""

    def test_re(self):
        correctness_pattern = re.compile('pattern')
        config = OutlierConfiguration(correctness_pattern=correctness_pattern)
        subject = create_task_rejector(config=config)

        self.assertEquals(correctness_pattern, subject.correctness_pattern)

    def test_bson_regex(self):
        pattern = 'pattern'
        flags = re.IGNORECASE
        correctness_pattern = bson.Regex(pattern, flags=flags)
        config = OutlierConfiguration(correctness_pattern=correctness_pattern)
        subject = create_task_rejector(config=config)

        self.assertNotEquals(correctness_pattern, subject.correctness_pattern)
        self.assertEquals(pattern, subject.correctness_pattern.pattern)
        self.assertEquals(flags, subject.correctness_pattern.flags)


class TestTaskCanary(unittest.TestCase):
    """Tests for TaskRejector.canary."""

    def test_is_canary(self):
        task = create_task_rejector()
        for test in ['canary_ping', 'canary_server', 'fio_thing', 'NetworkBandwidth']:
            mock_test = MagicMock(name='test', test=test)
            self.assertTrue(task.canary(mock_test))

    def test_not_canary(self):
        task = create_task_rejector()
        for test in ['distinct_types_no_predicate-useAgg', 'find-useAgg']:
            mock_test = MagicMock(name='test', test=test)
            self.assertFalse(task.canary(mock_test))


class TestTaskHasMinimumPoints(unittest.TestCase):
    """Tests for TaskRejector.has_minimum_points."""

    def test_too_little(self):
        task = create_task_rejector()
        for size in range(DEFAULT_CONFIG.minimum_points):
            mock_test = MagicMock(name='test', full_series={'size': size})
            self.assertFalse(task.has_minimum_points(mock_test))

    def test_enough(self):
        task = create_task_rejector()
        for size in range(DEFAULT_CONFIG.minimum_points, DEFAULT_CONFIG.minimum_points * 2):
            mock_test = MagicMock(name='test', full_series={'size': size})
            self.assertTrue(task.has_minimum_points(mock_test))


class TestTaskTooManyRejections(unittest.TestCase):
    """Tests for TaskRejector.too_many_rejections."""

    def test_empty(self):
        task = create_task_rejector()
        mock_test = MagicMock(name='test', full_series={'rejected': []})
        self.assertFalse(task.too_many_rejections(mock_test))

    def test_one(self):
        task = create_task_rejector()
        mock_test = MagicMock(name='test', full_series={'rejected': [True]})
        self.assertFalse(task.too_many_rejections(mock_test))

    def test_two(self):
        task = create_task_rejector()
        mock_test = MagicMock(name='test', full_series={'rejected': [True, True]})
        self.assertFalse(task.too_many_rejections(mock_test))

    def test_three(self):
        task = create_task_rejector()
        mock_test = MagicMock(name='test', full_series={'rejected': [True, True, True]})
        self.assertTrue(task.too_many_rejections(mock_test))

    def test_broken(self):
        task = create_task_rejector()
        mock_test = MagicMock(name='test', full_series={'rejected': [True, True, False, True]})
        self.assertFalse(task.too_many_rejections(mock_test))


class TestTaskLatest(unittest.TestCase):
    """Tests for TaskRejector.latest."""

    def test_not_latest(self):
        task = create_task_rejector(order=100)
        mock_test = MagicMock(name='test', full_series={'orders': [101]})
        self.assertFalse(task.latest(mock_test))

    def test_latest(self):
        task = create_task_rejector(order=100)
        orders = list(range(90, 101))
        for i in range(len(orders)):
            mock_test = MagicMock(name='test', full_series={'orders': orders[:i + 1]})
            self.assertTrue(task.latest(mock_test))
