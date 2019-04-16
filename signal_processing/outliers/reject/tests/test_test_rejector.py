"""
Unit tests for signal_processing/outliers/task.py.
"""
# pylint: disable=missing-docstring
from __future__ import print_function

import os
import unittest

import pymongo
from mock import MagicMock, patch, PropertyMock

from signal_processing.outliers.reject.tests.helper import create_test_rejector, test_identifier
from test_lib.fixture_files import FixtureFiles

NS = 'signal_processing.outliers.reject.task'
FIXTURE_FILES = FixtureFiles(os.path.dirname(__file__))


def ns(relative_name):  # pylint: disable=invalid-name
    """Return a full name from a name relative to the tested module's name space."""
    return NS + '.' + relative_name


class TestTestAutoRejector(unittest.TestCase):
    """Tests for TestAutoRejector."""

    def setUp(self):
        self.subject, _, _ = create_test_rejector()

    def test_ctor(self):
        self.assertEquals(self.subject.test_identifier, test_identifier())
        self.assertEquals(self.subject.test, 'test_name')
        self.assertEquals(self.subject.thread_level, '1')

    def test_config(self):
        with patch(ns('combine_outlier_configs')) as mock_combine_outlier_configs:
            # self.subject.task._configuration_model = mock_configuration_model
            self.subject._config = None

            mock_config = mock_combine_outlier_configs.return_value
            self.assertEquals(mock_config, self.subject.config)
            self.assertEquals(mock_config, self.subject.config)

            self.subject.task.configuration_model.get_configuration.assert_called_once_with(
                self.subject.test_identifier)
            mock_combine_outlier_configs.assert_called_once_with(
                self.subject.test_identifier,
                self.subject.task.configuration_model.get_configuration.return_value,
                self.subject.override_config)

    def test_full_series(self):
        self.assertDictContainsSubset({
            'test_identifier': test_identifier()
        }, self.subject.full_series)


class TestCanary(unittest.TestCase):
    """Tests for TestAutoRejector.canary."""

    def setUp(self):
        self.subject, _, _ = create_test_rejector()

    def test_canary(self):
        self.assertEquals(self.subject.task.canary.return_value, self.subject.canary)
        self.assertEquals(self.subject.task.canary.return_value, self.subject.canary)
        self.subject.task.canary.assert_called_once_with(self.subject)


class TestHasMinimumPoints(unittest.TestCase):
    """Tests for TestAutoRejector.has_minimum_points."""

    def setUp(self):
        self.subject, _, _ = create_test_rejector()

    def test_too_many_rejections(self):
        self.assertEquals(self.subject.task.has_minimum_points.return_value,
                          self.subject.has_minimum_points)
        self.assertEquals(self.subject.task.has_minimum_points.return_value,
                          self.subject.has_minimum_points)
        self.subject.task.has_minimum_points.assert_called_once_with(self.subject)


class TestTooManyRejections(unittest.TestCase):
    """Tests for TestAutoRejector.too_many_rejections."""

    def setUp(self):
        self.subject, _, _ = create_test_rejector()

    def test_too_many_rejections(self):
        self.assertEquals(self.subject.task.too_many_rejections.return_value,
                          self.subject.too_many_rejections)
        self.assertEquals(self.subject.task.too_many_rejections.return_value,
                          self.subject.too_many_rejections)
        self.subject.task.too_many_rejections.assert_called_once_with(self.subject)


class TestLatest(unittest.TestCase):
    """Tests for TestAutoRejector.latest."""

    def setUp(self):
        self.subject, _, _ = create_test_rejector()

    def test_too_many_rejections(self):
        self.assertEquals(self.subject.task.latest.return_value, self.subject.latest)
        self.assertEquals(self.subject.task.latest.return_value, self.subject.latest)
        self.subject.task.latest.assert_called_once_with(self.subject)


class TestMuted(unittest.TestCase):
    """Tests for muted."""

    def _test(self, mutes=False, enabled=False, expired=True):
        mock_mute = MagicMock(name='mute')
        mutes_collection = MagicMock(name='mute_outliers')
        rejector, _, mock_task = create_test_rejector()
        mock_task.points_model.db.__getitem__.return_value = mutes_collection

        if mutes:
            iterator = iter([mock_mute])
        else:
            iterator = iter([])

        mock_mute.get.return_value = enabled

        mutes_collection.find.return_value.sort.return_value.limit.return_value = iterator

        with patch(ns('mute_expired')) as mock_mute_expired:
            if not mutes:
                self.assertFalse(rejector.muted)
                mock_mute_expired.assert_not_called()
            else:
                mock_mute_expired.return_value = expired
                self.assertEquals(not expired, rejector.muted)
                if enabled:
                    mock_mute_expired.assert_called_once_with(mock_mute,
                                                              mock_task.points_model.db.points)
                mock_mute.get.assert_called_once_with('enabled', True)

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

    def test_not_enabled(self):
        self._test(mutes=True, enabled=False)

    def test_enabled(self):
        self._test(mutes=True, enabled=True)

    def test_active_mute(self):
        self._test(mutes=True, enabled=True, expired=False)


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


class TestReject(unittest.TestCase):
    """Tests for reject."""

    def create_subject(self, last_order=100, orders_range=None, test='canary_server-sleep-10ms'):
        if orders_range is None:
            orders_range = last_order + 1
        subject, _, _ = create_test_rejector(
            test=test, last_order=last_order, orders=range(orders_range))
        return subject

    def _test(self,
              order=10,
              outlier_orders=None,
              canary=True,
              muted=False,
              too_many_rejections=False,
              has_minimum_points=True,
              latest=True):
        """
        Setup the test with all the default conditions required for reject True.

        :param int order:  The current order.
        :param list outlier_orders: The outlier orders. If None then a list is created including
        the current order.
        :param bool canary: Is this a canary test. Defaults to True.
        :param bool muted: Is this test muted . Defaults to False.
        :param bool too_many_rejections:  Are there too many rejections. Defaults to False.
        :param bool has_minimum_points:  Are there a min number of points. Defaults to True.
        :param latest: Is this the latest order. Defaults to True.
        :return: The result of the reject call.
        """

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
            subject = self.create_subject(last_order=order)
            if outlier_orders is None:
                subject._outlier_orders = list(range(order + 1))
            return subject.reject(order)

    def test_reject(self):
        self.assertTrue(self._test())

    def test_not_outlier(self):
        order = 10
        self.assertFalse(self._test(order=order, outlier_orders=list(range(order))))

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
