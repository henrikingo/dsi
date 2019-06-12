"""
Change points detection related tests.
"""
import types
import unittest
from itertools import combinations, islice

import numpy as np
from numpy.testing import assert_array_equal
from mock import patch

from bin.common.log import setup_logging
from test_lib import math_utils
from signal_processing.change_points.detection import ChangePointsDetection, _calculate_magnitude, \
    create_outlier_mask
from signal_processing.change_points.e_divisive import EDivisive

setup_logging(False)

NS = 'signal_processing.change_points.detection'


def ns(relative_name):  # pylint: disable=invalid-name
    """Return a full name from a name relative to the tested module's name space."""
    return NS + '.' + relative_name


def create_revisions(length, iterable=None, size=None):
    """
    Create the revisions array.

    :param int length: The number of revisions to generate.
    :param iter iterable: The iterable to create revisions from. iterable is the alphabet 2 if no
    value is provided.
    :type iterable: iter or None.
    :param size: The size of revision from the iterable. size is 2 if no value is provided.
    :type size: int or None.
    :return: A list of strings.
    """
    iterable = "aabcdefghijklmnopqrstuvwxyz" if iterable is None else iterable
    size = 2 if size is None else size
    revisions = [
        "".join(combination) for combination in islice(combinations(iterable, size), length)
    ]
    return revisions


class TestCreateOutlierMask(unittest.TestCase):
    """
    Test Suite for create_outlier_mask.
    """

    def _test(self, outlier=None, marked=None, rejected=None, whitelisted=None, expected=None):
        """
        Test where outlier, marked, not rejected, not whitelisted.
        """
        outlier = outlier if outlier is not None else [False]
        length = len(outlier)

        expected = np.array(expected if expected is not None else outlier, dtype=np.bool)

        time_series = {
            'outlier': outlier if outlier is not None else [False],
            'marked': marked if marked is not None else [False] * length,
            'rejected': rejected if rejected is not None else [False] * length,
            'whitelisted': whitelisted if whitelisted is not None else [False] * length
        }
        mask = create_outlier_mask(time_series)
        assert_array_equal(expected, mask)

    def test_single_result_not_outlier(self):

        # no_nm_nr_nw
        self._test()  # expected mask = False

        # no_nm_nr_w
        self._test(whitelisted=[True])  # expected mask = False

        # no_nm_r_nw
        self._test(rejected=[True], expected=[True])  # expected mask = True

        # no_nm_r_w
        self._test(rejected=[True], whitelisted=[True])  # expected mask = False

        # no_m_nr_nw
        self._test(marked=[True], expected=[True])  # mask = True

        # no_m_nr_w
        self._test(marked=[True], whitelisted=[True], expected=[True])  # mask = False

        # no_m_r_nw
        self._test(marked=[True], rejected=[True], expected=[True])  # mask = True

        # no_m_r_w
        self._test(
            marked=[True], rejected=[True], whitelisted=[True], expected=[True])  # mask = False

    def test_single_result_outlier(self):

        # o_nm_nr_nw
        self._test(outlier=[True])  # expected mask = False

        # o_nm_nr_w
        self._test(outlier=[True], whitelisted=[True])  # expected mask = False

        # o_nm_r_nw
        self._test(outlier=[True], rejected=[True])  # expected mask = True

        # o_nm_r_w
        self._test(outlier=[True], rejected=[True], whitelisted=[True])  # expected mask = False

        # o_m_nr_nw
        self._test(outlier=[True], marked=[True])  # mask = True

        # o_m_nr_w
        self._test(outlier=[True], marked=[True], whitelisted=[True])  # mask = False

        # o_m_r_nw
        self._test(outlier=[True], marked=[True], rejected=[True])  # mask = True

        # o_m_r_w
        self._test(
            outlier=[True], marked=[True], rejected=[True], whitelisted=[True])  # mask = False

    def test_multiple(self):

        outlier = [False] * 2
        self._test(outlier=outlier)

        outlier = [True] * 2
        self._test(outlier=outlier)

        outlier = [True, False]
        self._test(outlier=outlier)

        outlier = [False, True, False]
        self._test(outlier=outlier)

        outlier = [False, True, False]
        self._test(outlier=outlier, marked=[True, False, True], expected=[True, True, True])


class TestPostRunCheck(unittest.TestCase):
    """
    Test post run check.
    """
    NUMBER_TYPES = (types.IntType, types.LongType, types.FloatType, types.ComplexType)

    @patch(ns('get_githashes_in_range_repo'))
    def test_random_ish_data(self, mock_git):
        """
        A cheeky test that noisy-looking data (random numbers generated from disjoint
        intervals) finds regressions. More of a regression-check than anything.
        """
        # from random import *
        # series = [ randint(150, 250) for _ in range(0,20) ]
        # print(series)
        # randint(1,50)
        series = [
            41,
            18,
            23,
            3,
            32,
            11,
            40,
            13,
            29,
            48,
            47,
            35,
            18,
            21,
            6,
            2,
            23,
            3,
            4,
            7,
            # randint(60,120)
            120,
            103,
            102,
            81,
            71,
            62,
            115,
            61,
            108,
            63,
            70,
            98,
            65,
            96,
            64,
            74,
            70,
            113,
            90,
            114,
            # randint(150,250)
            208,
            196,
            153,
            150,
            225,
            179,
            206,
            165,
            177,
            151,
            218,
            217,
            244,
            245,
            229,
            195,
            225,
            229,
            176,
            250
        ]
        length = len(series)
        state = {
            'testname':
                u'whatever you want, sugar',
            'series':
                series,
            'revisions': [
                'aa', 'ab', 'ac', 'ad', 'ae', 'af', 'ag', 'ah', 'ai', 'aj', 'ak', 'al', 'am', 'an',
                'ao', 'ap', 'aq', 'ar', 'as', 'at', 'ba', 'bb', 'bc', 'bd', 'be', 'bf', 'bg', 'bh',
                'bi', 'bj', 'bk', 'bl', 'bm', 'bn', 'bo', 'bp', 'bq', 'br', 'bs', 'bt', 'ca', 'cb',
                'cc', 'cd', 'ce', 'cf', 'cg', 'ch', 'ci', 'cj', 'ck', 'cl', 'cm', 'cn', 'co', 'cp',
                'cq', 'cr', 'cs', 'ct'
            ],
            'orders': [
                1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23,
                24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44,
                45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60
            ],
            'create_times': [
                1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23,
                24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44,
                45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60
            ],
            'thread_level':
                4,
            'outlier': [False] * length,
            'marked': [False] * length,
            'rejected': [False] * length,
            'whitelisted': [False] * length,
        }
        pvalue = 0.01
        permutations = 100
        mock_git.return_value = ['1', '2']

        algo = EDivisive(pvalue, permutations)
        detection = ChangePointsDetection(algo)
        points = detection.detect_change_points(state)

        self.assertEqual(3, len(points))

        self.assertDictContainsSubset(
            math_utils.approx_dict({
                'probability': 1.0,
                'suspect_revision': 'ca',
                'all_suspect_revisions': ['1', '2'],
                'create_time': 41,
                'thread_level': 4,
                'order': 41,
                'order_of_change_point': 0
            }), math_utils.approx_dict(points[0]))
        self.assertDictContainsSubset(
            math_utils.approx_dict({
                'name': 'E-Divisive',
                'index': 40,
                'window_size': 60,
                'value_to_avg': 26.9,
                'average_diff': 88.7766666667,
                'average': 103.366666667,
                'value': 2776.9,
                'value_to_avg_diff': 31.3,
                'probability': 0.0,
            }), math_utils.approx_dict(points[0]['algorithm']))
        self.assertDictContainsSubset(
            math_utils.approx_dict({
                'probability': 1.0,
                'suspect_revision': 'ba',
                'create_time': 21,
                'thread_level': 4,
                'order': 21,
                'order_of_change_point': 1
            }), math_utils.approx_dict(points[1]))
        self.assertDictContainsSubset(
            math_utils.approx_dict({
                'name': 'E-Divisive',
                'index': 20,
                'window_size': 40,
                'value_to_avg': 16.5,
                'average_diff': 42.9325,
                'average': 54.1,
                'value': 893.6,
                'value_to_avg_diff': 20.8,
                'probability': 0.0,
            }), math_utils.approx_dict(points[1]['algorithm']))
        self.assertDictContainsSubset(
            math_utils.approx_dict({
                'probability': 1.0,
                'suspect_revision': 'ck',
                'create_time': 51,
                'thread_level': 4,
                'order': 51,
                'order_of_change_point': 2
            }), math_utils.approx_dict(points[2]))
        self.assertDictContainsSubset(
            math_utils.approx_dict({
                'name': 'E-Divisive',
                'index': 50,
                'window_size': 20,
                'value_to_avg': 0.8,
                'average_diff': 36.1,
                'average': 201.9,
                'value': 167.7,
                'value_to_avg_diff': 4.6,
                'probability': 0.0,
            }), math_utils.approx_dict(points[2]['algorithm']))

    # pylint: disable=no-self-use
    def _test_helper(self, series=None, outlier=None, marked=None, rejected=None, whitelisted=None):
        """
        Helper for simple regression test.
        """
        if series is None:
            series = np.full(30, 50, dtype=np.int)
            series[15:30] = 100
        length = len(series)
        values = list(range(length))
        revisions = create_revisions(length)

        with patch(ns('get_githashes_in_range_repo')):
            state = {
                'testname': u'whatever you want, sugar',
                'series': series,
                'revisions': revisions,
                'orders': values,
                'create_times': values,
                'thread_level': 4,
                'outlier': outlier if outlier is not None else [False] * length,
                'marked': marked if marked is not None else [False] * length,
                'rejected': rejected if rejected is not None else [False] * length,
                'whitelisted': whitelisted if whitelisted is not None else [False] * length,
            }
            pvalue = 0.01
            permutations = 100

            algo = EDivisive(pvalue, permutations)
            detection = ChangePointsDetection(algo)
            points = detection.detect_change_points(state)
            points = sorted(points, key=lambda i: i['order'])
        return points, state

    def test_finds_simple_regression(self):
        """
        Test finding a simple regression.
        """
        points, state = self._test_helper()
        expected = 15

        self.assertEqual(1, len(points))
        self.assertDictContainsSubset({
            'probability': 1.0,
            'suspect_revision': state['revisions'][expected],
            'create_time': expected,
            'thread_level': 4,
            'order': expected,
        }, math_utils.approx_dict(points[0]))

    def test_simple_with_outliers(self):
        """
        Test finding a simple regression.
        """
        expected = 18
        outlier = np.full(30, False, dtype=np.bool)
        outlier[expected - 3:expected] = True

        points, state = self._test_helper(outlier=outlier)

        self.assertEqual(1, len(points))
        self.assertDictContainsSubset({
            'probability': 1.0,
            'suspect_revision': state['revisions'][expected],
            'create_time': expected,
            'thread_level': 4,
            'order': expected,
        }, math_utils.approx_dict(points[0]))

    def test_finds_ahead(self):
        """
        Test ahead.
        """
        series = [50] * 14 + [74] + [100] * 15
        points, state = self._test_helper(series=series)

        self.assertEqual(1, len(points))
        expected = 15
        self.assertDictContainsSubset({
            'probability': 1.0,
            'suspect_revision': state['revisions'][expected],
            'create_time': expected,
            'thread_level': 4,
            'order': expected,
            'value': 100
        }, math_utils.approx_dict(points[0]))

    def test_finds_behind(self):
        """
        Test finding behind.
        """
        series = np.full(30, 50, dtype=np.int)
        series[14] = 76
        series[15:30] = 100

        points, state = self._test_helper(series=series)

        expected = 14
        self.assertEqual(1, len(points))
        self.assertDictContainsSubset({
            'probability': 1.0,
            'suspect_revision': state['revisions'][expected],
            'create_time': expected,
            'thread_level': 4,
            'order': expected,
            'value': 76
        }, math_utils.approx_dict(points[0]))

    def test_finds_simple_regression2(self):
        """
        Test another simple regression.
        """
        series = np.full(30, 50, dtype=np.int)
        series[2] = 100
        series[15:30] = 100

        points, state = self._test_helper(series=series)

        expected = 15

        self.assertEqual(1, len(points))

        self.assertDictContainsSubset(
            math_utils.approx_dict({
                'probability': 1.0,
                'suspect_revision': state['revisions'][expected],
                'create_time': expected,
                'thread_level': 4,
                'order': expected,
                'order_of_change_point': 0
            }), math_utils.approx_dict(points[0]))
        self.assertDictContainsSubset(
            math_utils.approx_dict({
                'name': 'E-Divisive',
                'index': 15,
                'window_size': 30,
                'value_to_avg': 7.9,
                'average_diff': 24.9,
                'average': 76.7,
                'value': 606.7,
                'value_to_avg_diff': 24.4,
                'probability': 0.0,
            }), math_utils.approx_dict(points[0]['algorithm']))

    def test_regression_and_recovery(self):
        """
        Test regression and recovery.
        """
        # create an array filled with 50s' then set some ranges to 100
        series = np.full(45, 50, dtype=np.int)
        series[2] = 100
        series[15:30] = 100
        series[32] = 100

        points, state = self._test_helper(series=series)

        expected = 15
        self.assertEqual(2, len(points))
        self.assertDictContainsSubset(
            math_utils.approx_dict({
                'probability': 1.0,
                'suspect_revision': state['revisions'][expected],
                'create_time': expected,
                'thread_level': 4,
                'order': expected,
                'value': 100,
                'order_of_change_point': 1
            }), math_utils.approx_dict(points[0]))
        self.assertDictContainsSubset(
            math_utils.approx_dict({
                'name': 'E-Divisive',
                'index': 15,
                'window_size': 33,
                'value_to_avg': 7.0,
                'average_diff': 25.0,
                'average': 75.8,
                'value': 532.6,
                'value_to_avg_diff': 21.3,
                'probability': 0.0,
            }), math_utils.approx_dict(points[0]['algorithm']))

        expected = 33
        self.assertDictContainsSubset(
            math_utils.approx_dict({
                'probability': 1.0,
                'suspect_revision': state['revisions'][expected],
                'create_time': expected,
                'thread_level': 4,
                'order': expected,
                'order_of_change_point': 0
            }), math_utils.approx_dict(points[1]))
        self.assertDictContainsSubset(
            math_utils.approx_dict({
                'name': 'E-Divisive',
                'index': 33,
                'window_size': 45,
                'value_to_avg': 3.0,
                'average_diff': 23.5,
                'average': 68.9,
                'value': 206.1,
                'value_to_avg_diff': 8.8,
                'probability': 0.0,
            }), math_utils.approx_dict(points[1]['algorithm']))

    # pylint: disable=invalid-name
    def _test_regression_and_recovery_outliers(self, series, outlier, marked=None):
        """
        Test regression and recovery helper.
        """
        points, state = self._test_helper(series=series, outlier=outlier, marked=marked)
        expected = 18

        self.assertEqual(2, len(points))
        self.assertDictContainsSubset(
            math_utils.approx_dict({
                'probability': 1.0,
                'suspect_revision': state['revisions'][expected],
                'create_time': expected,
                'thread_level': 4,
                'order': expected,
                'value': 100,
                'order_of_change_point': 0
            }), math_utils.approx_dict(points[0]))
        self.assertDictContainsSubset(
            math_utils.approx_dict({
                'name': 'E-Divisive',
                'index': 18,
                'window_size': 40,
                'value_to_avg': 2.8,
                'average_diff': 21.0,
                'average': 65.0,
                'value': 182.8,
                'value_to_avg_diff': 8.7,
                'probability': 0.0,
            }), math_utils.approx_dict(points[0]['algorithm']))

        expected = 30
        self.assertDictContainsSubset(
            math_utils.approx_dict({
                'probability': 1.0,
                'suspect_revision': state['revisions'][expected],
                'create_time': expected,
                'thread_level': 4,
                'order': expected,
                'order_of_change_point': 1
            }), math_utils.approx_dict(points[1]))
        self.assertDictContainsSubset(
            math_utils.approx_dict({
                'name': 'E-Divisive',
                'index': 30,
                'window_size': 26,
                'value_to_avg': 8.2,
                'average_diff': 24.9,
                'average': 73.1,
                'value': 600.0,
                'value_to_avg_diff': 24.1,
                'probability': 0.0,
            }), math_utils.approx_dict(points[1]['algorithm']))

    # pylint: disable=invalid-name
    def test_regression_and_recovery_outliers(self):
        """
        Test regression and recovery.
        """
        length = 45
        series = np.full(length, 50, dtype=np.int)
        series[2] = 100
        series[15:30] = 100
        series[32] = 100

        outlier = np.full(length, False, dtype=np.bool)
        outlier[2] = True
        outlier[15:18] = True
        outlier[32] = True

        self._test_regression_and_recovery_outliers(series, outlier)

    # pylint: disable=invalid-name
    def test_regression_and_recovery_outliers_marked(self):
        """
        Test regression and recovery marked.
        """
        length = 45

        series = np.full(length, 50, dtype=np.int)
        series[2] = 100
        series[15:30] = 100
        series[32] = 100

        outlier = np.full(length, False, dtype=np.bool)

        marked = np.full(length, False, dtype=np.bool)
        marked[2] = True
        marked[15:18] = True
        marked[32] = True

        self._test_regression_and_recovery_outliers(series, outlier, marked=marked)

    def test_two_regressions(self):
        """
        Test 2 regressions.
        """
        length = 45

        series = np.full(length, 50, dtype=np.int)
        series[2] = 100
        series[15:30] = 100
        series[30:] = 150

        points, state = self._test_helper(series=series)

        expected = 15
        self.assertEqual(2, len(points))
        self.assertDictContainsSubset(
            math_utils.approx_dict({
                'probability': 1.0,
                'suspect_revision': state['revisions'][expected],
                'create_time': expected,
                'thread_level': 4,
                'order': expected,
                'order_of_change_point': 1
            }), math_utils.approx_dict(points[0]))
        self.assertDictContainsSubset(
            math_utils.approx_dict({
                'name': 'E-Divisive',
                'index': 15,
                'window_size': 30,
                'value_to_avg': 7.9,
                'average_diff': 24.9,
                'average': 76.7,
                'value': 606.7,
                'value_to_avg_diff': 24.4,
                'probability': 0.0,
            }), math_utils.approx_dict(points[0]['algorithm']))
        self.assertDictContainsSubset(
            math_utils.approx_dict({
                'nobs': 14,
                'minmax': (100, 100),
                'mean': 100.0,
                'variance': 0.0,
                'skewness': 0.0,
                'kurtosis': -3.0
            }), math_utils.approx_dict(points[0]['statistics']['next']))
        self.assertDictContainsSubset(
            math_utils.approx_dict({
                'nobs': 14,
                'minmax': (50, 100),
                'mean': 53.6,
                'variance': 178.6,
                'skewness': 3.3,
                'kurtosis': 9.1
            }), math_utils.approx_dict(points[0]['statistics']['previous']))

        expected = 30
        self.assertDictContainsSubset(
            math_utils.approx_dict({
                'probability': 1.0,
                'suspect_revision': state['revisions'][expected],
                'create_time': expected,
                'thread_level': 4,
                'order': expected,
                'order_of_change_point': 0
            }), math_utils.approx_dict(points[1]))
        self.assertDictContainsSubset(
            math_utils.approx_dict({
                'name': 'E-Divisive',
                'index': 30,
                'window_size': 45,
                'value_to_avg': 12.0,
                'average_diff': 43.7,
                'average': 101.1,
                'value': 1209.2,
                'value_to_avg_diff': 27.7,
                'probability': 0.0,
            }), math_utils.approx_dict(points[1]['algorithm']))

    def test_two_regressions_outliers(self):
        """
        Test 2 regressions.
        """
        length = 45

        series = np.full(length, 50, dtype=np.int)
        series[2] = 100
        series[15:30] = 100
        series[30:] = 150

        outlier = np.full(length, False, dtype=np.bool)
        outlier[2] = True
        outlier[15:18] = True
        outlier[30:33] = True

        points, state = self._test_helper(series=series, outlier=outlier)

        expected = 18
        self.assertEqual(2, len(points))
        self.assertDictContainsSubset(
            math_utils.approx_dict({
                'probability': 1.0,
                'suspect_revision': state['revisions'][expected],
                'create_time': expected,
                'thread_level': 4,
                'order': expected,
                'order_of_change_point': 1
            }), math_utils.approx_dict(points[0]))
        self.assertDictContainsSubset(
            math_utils.approx_dict({
                'name': 'E-Divisive',
                'index': 18,
                'window_size': 26,
                'value_to_avg': 8.2,
                'average_diff': 24.9,
                'average': 73.1,
                'value': 600.0,
                'value_to_avg_diff': 24.1,
                'probability': 0.0,
            }), math_utils.approx_dict(points[0]['algorithm']))
        self.assertDictContainsSubset(
            math_utils.approx_dict({
                'nobs': 11,
                'minmax': (100, 100),
                'mean': 100.0,
                'variance': 0.0,
                'skewness': 0.0,
                'kurtosis': -3.0
            }), math_utils.approx_dict(points[0]['statistics']['next']))
        self.assertDictContainsSubset(
            math_utils.approx_dict({
                'nobs': 13,
                'minmax': (50, 50),
                'mean': 50.0,
                'variance': 0.0,
                'skewness': 0.0,
                'kurtosis': -3.0
            }), math_utils.approx_dict(points[0]['statistics']['previous']))

        expected = 33
        self.assertDictContainsSubset(
            math_utils.approx_dict({
                'probability': 1.0,
                'suspect_revision': state['revisions'][expected],
                'create_time': expected,
                'thread_level': 4,
                'order': expected,
                'order_of_change_point': 0
            }), math_utils.approx_dict(points[1]))
        self.assertDictContainsSubset(
            math_utils.approx_dict({
                'name': 'E-Divisive',
                'index': 33,
                'window_size': 38,
                'value_to_avg': 10.5,
                'average_diff': 44.9,
                'average': 97.4,
                'value': 1024.0,
                'value_to_avg_diff': 22.8,
                'probability': 0.0,
            }), math_utils.approx_dict(points[1]['algorithm']))
        self.assertDictContainsSubset(
            math_utils.approx_dict({
                'nobs': 11,
                'minmax': (100, 100),
                'mean': 100.0,
                'variance': 0.0,
                'skewness': 0.0,
                'kurtosis': -3.0
            }), math_utils.approx_dict(points[1]['statistics']['previous']))
        self.assertDictContainsSubset(
            math_utils.approx_dict({
                'nobs': 12,
                'minmax': (150, 150),
                'mean': 150.0,
                'variance': 0.0,
                'skewness': 0.0,
                'kurtosis': -3.0
            }), math_utils.approx_dict(points[1]['statistics']['next']))

    def test_no_regressions(self):
        """
        Test no regression.
        """
        series = np.full(30, 50, dtype=np.int)
        points, _ = self._test_helper(series=series)
        self.assertEqual(0, len(points))

    def test_no_regressions_with_outliers_start(self):
        """
        Test no regression with outliers.
        """
        length = 30
        series = np.full(length, 50, dtype=np.int)

        outlier = np.full(length, False, dtype=np.bool)
        outlier[0] = True

        points, _ = self._test_helper(series=series, outlier=outlier)
        self.assertEqual(0, len(points))

    def test_no_regressions_with_outliers_end(self):
        """
        Test no regression with outliers.
        """
        length = 30
        series = np.full(length, 50, dtype=np.int)

        outlier = np.full(length, False, dtype=np.bool)
        outlier[-1] = True

        points, _ = self._test_helper(series=series, outlier=outlier)
        self.assertEqual(0, len(points))

    def test_no_regressions_with_outliers_middle(self):
        """
        Test no regression with outliers.
        """
        length = 30
        series = np.full(length, 50, dtype=np.int)

        outlier = np.full(length, False, dtype=np.bool)
        outlier[18:21] = True

        points, _ = self._test_helper(series=series, outlier=outlier)
        self.assertEqual(0, len(points))

    def test_outliers_masked(self):
        """
        Test with all outliers masked.
        """
        length = 81
        series = np.full(length, 50, dtype=np.int)
        series[19:31] = 100
        series[50:62] = 200

        outlier = np.full(length, False, dtype=np.bool)
        outlier[19:31] = True
        outlier[50:62] = True

        points, _ = self._test_helper(series=series, outlier=outlier)
        self.assertEqual(0, len(points))

    def test_outliers_nothing_masked(self):
        """
        Test with outliers, nothing masked.
        """
        series = np.full(81, 50, dtype=np.int)
        series[19:31] = 100
        series[50:62] = 200
        outlier = [False] * len(series)
        points, _ = self._test_helper(series=series, outlier=outlier)
        self.assertGreater(len(points), 0)


class TestCalculateMagnitude(unittest.TestCase):
    """
    Test _calculate_magnitude.
    """

    def test_calculate_magnitude(self):
        """ Test _calculate_magnitude with a standard input. """
        statistics = {'previous': {'mean': 1}, 'next': {'mean': 2}}
        self.assertEqual(_calculate_magnitude(statistics), (np.log(2), 'Major Improvement'))

    def test_calculate_magnitude_none(self):
        """ Test _calculate_mean handles `None` values appropriately. """
        self.assertEqual(_calculate_magnitude(None), (None, 'Uncategorized'))

        statistics = {'next': {'mean': 2}}
        self.assertEqual(_calculate_magnitude(statistics), (None, 'Uncategorized'))

        statistics = {'previous': {'mean': 1}}
        self.assertEqual(_calculate_magnitude(statistics), (None, 'Uncategorized'))

    # pylint: disable=invalid-name
    def test_calculate_magnitude_latency(self):
        """ Test _calculate_magnitude distinguishes latency values. """
        statistics = {'previous': {'mean': -1}, 'next': {'mean': -2}}
        self.assertEqual(
            _calculate_magnitude(statistics), (np.log(float(1) / float(2)), 'Major Regression'))

    # pylint: disable=invalid-name
    def test_calculate_magnitude_previous_zero(self):
        """ Test _calculate_magnitude with a zero value for previous mean. """
        statistics = {'previous': {'mean': 0}, 'next': {'mean': 2}}
        self.assertEqual(_calculate_magnitude(statistics), (float('inf'), 'Major Improvement'))

        statistics = {'previous': {'mean': 0}, 'next': {'mean': -2}}
        self.assertEqual(_calculate_magnitude(statistics), (float('inf'), 'Major Improvement'))

    # pylint: disable=invalid-name
    def test_calculate_magnitude_next_zero(self):
        """ Test _calculate_magnitude with a zero value for next mean. """
        statistics = {'previous': {'mean': 2}, 'next': {'mean': 0}}
        self.assertEqual(_calculate_magnitude(statistics), (float('-inf'), 'Major Regression'))

        statistics = {'previous': {'mean': -2}, 'next': {'mean': 0}}
        self.assertEqual(_calculate_magnitude(statistics), (float('-inf'), 'Major Regression'))

    # pylint: disable=invalid-name
    def test_calculate_magnitude_categories_thresholds(self):
        """ Test that _calculate magnitude returns the correct categories around the thresholds. """
        statistics = {'previous': {'mean': np.e**.5 + 0.0000001}, 'next': {'mean': 1}}
        self.assertEqual(_calculate_magnitude(statistics)[1], 'Major Regression')

        statistics = {'previous': {'mean': np.e**.5}, 'next': {'mean': 1}}
        self.assertEqual(_calculate_magnitude(statistics)[1], 'Moderate Regression')

        statistics = {'previous': {'mean': np.e**.2 + 0.0000001}, 'next': {'mean': 1}}
        self.assertEqual(_calculate_magnitude(statistics)[1], 'Moderate Regression')

        statistics = {'previous': {'mean': np.e**.2}, 'next': {'mean': 1}}
        self.assertEqual(_calculate_magnitude(statistics)[1], 'Minor Regression')

        statistics = {'previous': {'mean': 1}, 'next': {'mean': 0.9999999}}
        self.assertEqual(_calculate_magnitude(statistics)[1], 'Minor Regression')

        statistics = {'previous': {'mean': 1}, 'next': {'mean': np.e**.5 + 0.0000001}}
        self.assertEqual(_calculate_magnitude(statistics)[1], 'Major Improvement')

        statistics = {'previous': {'mean': 1}, 'next': {'mean': np.e**.5}}
        self.assertEqual(_calculate_magnitude(statistics)[1], 'Moderate Improvement')

        statistics = {'previous': {'mean': 1}, 'next': {'mean': np.e**.2 + 0.0000001}}
        self.assertEqual(_calculate_magnitude(statistics)[1], 'Moderate Improvement')

        statistics = {'previous': {'mean': 1}, 'next': {'mean': np.e**.2}}
        self.assertEqual(_calculate_magnitude(statistics)[1], 'Minor Improvement')

        statistics = {'previous': {'mean': 1}, 'next': {'mean': 1}}
        self.assertEqual(_calculate_magnitude(statistics)[1], 'Minor Improvement')
