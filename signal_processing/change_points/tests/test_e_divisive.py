"""
E-Divisive related tests.
"""
import types
import unittest

import numpy as np
from mock import patch

from bin.common.log import setup_logging
from test_lib import math_utils
from signal_processing.change_points.e_divisive import EDivisive, calculate_magnitude

setup_logging(False)

NS = 'signal_processing.change_points.e_divisive'


def ns(relative_name):  # pylint: disable=invalid-name
    """Return a full name from a name relative to the tested module's name space."""
    return NS + '.' + relative_name


class TestEDivisive(unittest.TestCase):
    """
    Test for EDivisive class methods.
    """

    def test_series_none(self):
        """
        Test that constructor parameters are validated.
        """
        self.assertEqual(EDivisive({'series': None}).series.size, 0)

    def test_series_string(self):
        """
        Test that constructor parameters are validated.
        """
        with self.assertRaises(ValueError):
            EDivisive({'series': "string"})

    def test_series_empty(self):
        """
        Test that constructor parameters are validated.
        """
        EDivisive({'series': []})

    def test_empty_e_divisive(self):
        """
        Test that constructor parameters are validated.
        """
        self.assertEqual(EDivisive({}).qhat_values(np.array([], dtype=np.float)).size, 0)


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
                4
        }
        pvalue = 0.01
        permutations = 100
        mock_git.return_value = ['1', '2']
        algo = EDivisive(state, pvalue, permutations)
        points = algo.change_points
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

    @patch(ns('get_githashes_in_range_repo'))
    def test_finds_simple_regression(self, mock_git):
        """
        Test finding a simple regression.
        """
        state = {
            'testname':
                u'whatever you want, sugar',
            'series': [
                50, 50, 50, 50, 50, 50, 50, 50, 50, 50, 50, 50, 50, 50, 50, 100, 100, 100, 100, 100,
                100, 100, 100, 100, 100, 100, 100, 100, 100, 100
            ],
            'revisions': [
                'aa', 'ab', 'ac', 'ad', 'ae', 'af', 'ag', 'ah', 'ai', 'aj', 'ak', 'al', 'am', 'an',
                'ao', 'ba', 'bb', 'bc', 'bd', 'be', 'bf', 'bg', 'bh', 'bi', 'bj', 'bk', 'bl', 'bm',
                'bn', 'bo'
            ],
            'orders': [
                1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23,
                24, 25, 26, 27, 28, 29, 30
            ],
            'create_times': [
                1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23,
                24, 25, 26, 27, 28, 29, 30
            ],
            'thread_level':
                4
        }
        pvalue = 0.01
        permutations = 100
        algo = EDivisive(state, pvalue, permutations)
        points = algo.change_points
        self.assertEqual(1, len(points))
        self.assertDictContainsSubset({
            'probability': 1.0,
            'suspect_revision': 'ba',
            'create_time': 16,
            'thread_level': 4,
            'order': 16,
        }, math_utils.approx_dict(points[0]))

    @patch(ns('get_githashes_in_range_repo'))
    def test_finds_ahead(self, mock_git):
        """
        Test ahead.
        """
        series = [50] * 14 + [74] + [100] * 15
        state = {
            'testname': u'ahoy! Regression ahead.',
            'series': series,
            'revisions': range(len(series)),
            'orders': range(len(series)),
            'create_times': range(len(series)),
            'thread_level': 4
        }
        pvalue = 0.01
        permutations = 100
        algo = EDivisive(state, pvalue, permutations)
        points = algo.change_points
        self.assertEqual(1, len(points))
        self.assertDictContainsSubset({
            'probability': 1.0,
            'suspect_revision': 15,
            'create_time': 15,
            'thread_level': 4,
            'order': 15,
            'value': 100
        }, math_utils.approx_dict(points[0]))

    @patch(ns('get_githashes_in_range_repo'))
    def test_finds_behind(self, mock_git):
        """
        Test finding behind.
        """
        series = [50] * 14 + [76] + [100] * 15
        state = {
            'testname': u'Ahoy! Regression behind',
            'series': series,
            'revisions': range(len(series)),
            'orders': range(len(series)),
            'create_times': range(len(series)),
            'thread_level': 4
        }
        pvalue = 0.01
        permutations = 100
        algo = EDivisive(state, pvalue, permutations)
        points = algo.change_points
        self.assertEqual(1, len(points))
        self.assertDictContainsSubset({
            'probability': 1.0,
            'suspect_revision': 14,
            'create_time': 14,
            'thread_level': 4,
            'order': 14,
            'value': 76
        }, math_utils.approx_dict(points[0]))

    @patch(ns('get_githashes_in_range_repo'))
    def test_finds_simple_regression2(self, mock_git):
        """
        Test another simple regression.
        """
        state = {
            'testname':
                u'whatever you want, sugar',
            'series': [
                50, 50, 100, 50, 50, 50, 50, 50, 50, 50, 50, 50, 50, 50, 50, 100, 100, 100, 100,
                100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100
            ],
            'revisions': [
                'aa', 'ab', 'ac', 'ad', 'ae', 'af', 'ag', 'ah', 'ai', 'aj', 'ak', 'al', 'am', 'an',
                'ao', 'ba', 'bb', 'bc', 'bd', 'be', 'bf', 'bg', 'bh', 'bi', 'bj', 'bk', 'bl', 'bm',
                'bn', 'bo'
            ],
            'orders': [
                1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23,
                24, 25, 26, 27, 28, 29, 30
            ],
            'create_times': [
                1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23,
                24, 25, 26, 27, 28, 29, 30
            ],
            'thread_level':
                4
        }
        pvalue = 0.01
        permutations = 100
        algo = EDivisive(state, pvalue, permutations)
        points = algo.change_points
        self.assertEqual(1, len(points))

        self.assertDictContainsSubset(
            math_utils.approx_dict({
                'probability': 1.0,
                'suspect_revision': 'ba',
                'create_time': 16,
                'thread_level': 4,
                'order': 16,
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

    @patch(ns('get_githashes_in_range_repo'))
    def test_regression_and_recovery(self, mock_git):
        """
        Test regression and recovery.
        """
        state = {
            'testname':
                u'whatever you want, sugar',
            'series': [
                50, 50, 100, 50, 50, 50, 50, 50, 50, 50, 50, 50, 50, 50, 50, 100, 100, 100, 100,
                100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 50, 50, 100, 50, 50, 50, 50,
                50, 50, 50, 50, 50, 50, 50, 50
            ],
            'revisions': [
                'aa', 'ab', 'ac', 'ad', 'ae', 'af', 'ag', 'ah', 'ai', 'aj', 'ak', 'al', 'am', 'an',
                'ao', 'ba', 'bb', 'bc', 'bd', 'be', 'bf', 'bg', 'bh', 'bi', 'bj', 'bk', 'bl', 'bm',
                'bn', 'bo', 'ca', 'cb', 'cc', 'cd', 'ce', 'cf', 'cg', 'ch', 'ci', 'cj', 'ck', 'cl',
                'cm', 'cn', 'co'
            ],
            'orders': [
                1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23,
                24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44,
                45
            ],
            'create_times': [
                1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23,
                24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44,
                45
            ],
            'thread_level':
                4
        }
        pvalue = 0.01
        permutations = 100
        algo = EDivisive(state, pvalue, permutations)
        points = sorted(algo.change_points, key=lambda i: i['order'])
        self.assertEqual(2, len(points))
        self.assertDictContainsSubset(
            math_utils.approx_dict({
                'probability': 1.0,
                'suspect_revision': 'ba',
                'create_time': 16,
                'thread_level': 4,
                'order': 16,
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
        self.assertDictContainsSubset(
            math_utils.approx_dict({
                'probability': 1.0,
                'suspect_revision': 'cd',
                'create_time': 34,
                'thread_level': 4,
                'order': 34,
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

    @patch(ns('get_githashes_in_range_repo'))
    def test_two_regressions(self, mock_git):
        """
        Test 2 regressions.
        """
        state = {
            'testname':
                u'whatever you want, sugar',
            'series': [
                50, 50, 100, 50, 50, 50, 50, 50, 50, 50, 50, 50, 50, 50, 50, 100, 100, 100, 100,
                100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 150, 150, 150, 150, 150, 150,
                150, 150, 150, 150, 150, 150, 150, 150, 150
            ],
            'revisions': [
                'aa', 'ab', 'ac', 'ad', 'ae', 'af', 'ag', 'ah', 'ai', 'aj', 'ak', 'al', 'am', 'an',
                'ao', 'ba', 'bb', 'bc', 'bd', 'be', 'bf', 'bg', 'bh', 'bi', 'bj', 'bk', 'bl', 'bm',
                'bn', 'bo', 'ca', 'cb', 'cc', 'cd', 'ce', 'cf', 'cg', 'ch', 'ci', 'cj', 'ck', 'cl',
                'cm', 'cn', 'co'
            ],
            'orders': [
                1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23,
                24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44,
                45
            ],
            'create_times': [
                1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23,
                24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44,
                45
            ],
            'thread_level':
                4
        }
        pvalue = 0.01
        permutations = 100
        algo = EDivisive(state, pvalue, permutations)
        points = sorted(algo.change_points, key=lambda i: i['order'])
        self.assertEqual(2, len(points))
        self.assertDictContainsSubset(
            math_utils.approx_dict({
                'probability': 1.0,
                'suspect_revision': 'ba',
                'create_time': 16,
                'thread_level': 4,
                'order': 16,
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
        self.assertDictContainsSubset(
            math_utils.approx_dict({
                'probability': 1.0,
                'suspect_revision': 'ca',
                'create_time': 31,
                'thread_level': 4,
                'order': 31,
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

    def test_no_regressions(self):
        """
        Test no regression.
        """
        state = {
            'testname':
                u'whatever you want, sugar',
            'series': [
                50, 50, 50, 50, 50, 50, 50, 50, 50, 50, 50, 50, 50, 50, 50, 50, 50, 50, 50, 50, 50,
                50, 50, 50, 50, 50, 50, 50, 50, 50
            ],
            'revisions': [
                'aa', 'ab', 'ac', 'ad', 'ae', 'af', 'ag', 'ah', 'ai', 'aj', 'ak', 'al', 'am', 'an',
                'ao', 'ba', 'bb', 'bc', 'bd', 'be', 'bf', 'bg', 'bh', 'bi', 'bj', 'bk', 'bl', 'bm',
                'bn', 'bo'
            ],
            'orders': [
                1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23,
                24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44,
                44
            ],
            'create_times': [
                1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23,
                24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44,
                45
            ],
            'thread_level':
                4
        }
        pvalue = 0.01
        permutations = 100
        algo = EDivisive(state, pvalue, permutations)
        points = algo.change_points
        self.assertEqual(0, len(points))


class TestCalculateMagnitude(unittest.TestCase):
    """
    Test calculate_magnitude.
    """

    def test_calculate_magnitude(self):
        """ Test calculate_magnitude with a standard input. """
        statistics = {'previous': {'mean': 1}, 'next': {'mean': 2}}
        self.assertEqual(calculate_magnitude(statistics), (np.log(2), 'Major Improvement'))

    def test_calculate_magnitude_none(self):
        """ Test calculate_mean handles `None` values appropriately. """
        self.assertEqual(calculate_magnitude(None), (None, 'Uncategorized'))

        statistics = {'next': {'mean': 2}}
        self.assertEqual(calculate_magnitude(statistics), (None, 'Uncategorized'))

        statistics = {'previous': {'mean': 1}}
        self.assertEqual(calculate_magnitude(statistics), (None, 'Uncategorized'))

    def test_calculate_magnitude_latency(self):
        """ Test calculate_magnitude distinguishes latency values. """
        statistics = {'previous': {'mean': -1}, 'next': {'mean': -2}}
        self.assertEqual(
            calculate_magnitude(statistics), (np.log(float(1) / float(2)), 'Major Regression'))

    def test_calculate_magnitude_previous_zero(self):
        """ Test calculate_magnitude with a zero value for previous mean. """
        statistics = {'previous': {'mean': 0}, 'next': {'mean': 2}}
        self.assertEqual(calculate_magnitude(statistics), (float('inf'), 'Major Improvement'))

        statistics = {'previous': {'mean': 0}, 'next': {'mean': -2}}
        self.assertEqual(calculate_magnitude(statistics), (float('inf'), 'Major Improvement'))

    def test_calculuate_magnitude_next_zero(self):
        """ Test calculate_magnitude with a zero value for next mean. """
        statistics = {'previous': {'mean': 2}, 'next': {'mean': 0}}
        self.assertEqual(calculate_magnitude(statistics), (float('-inf'), 'Major Regression'))

        statistics = {'previous': {'mean': -2}, 'next': {'mean': 0}}
        self.assertEqual(calculate_magnitude(statistics), (float('-inf'), 'Major Regression'))

    def test_calculate_magnitude_categories_thresholds(self):
        """ Test that calculate magnitude returns the correct categories around the thresholds. """
        statistics = {'previous': {'mean': np.e**.5 + 0.0000001}, 'next': {'mean': 1}}
        self.assertEqual(calculate_magnitude(statistics)[1], 'Major Regression')

        statistics = {'previous': {'mean': np.e**.5}, 'next': {'mean': 1}}
        self.assertEqual(calculate_magnitude(statistics)[1], 'Moderate Regression')

        statistics = {'previous': {'mean': np.e**.2 + 0.0000001}, 'next': {'mean': 1}}
        self.assertEqual(calculate_magnitude(statistics)[1], 'Moderate Regression')

        statistics = {'previous': {'mean': np.e**.2}, 'next': {'mean': 1}}
        self.assertEqual(calculate_magnitude(statistics)[1], 'Minor Regression')

        statistics = {'previous': {'mean': 1}, 'next': {'mean': 0.9999999}}
        self.assertEqual(calculate_magnitude(statistics)[1], 'Minor Regression')

        statistics = {'previous': {'mean': 1}, 'next': {'mean': np.e**.5 + 0.0000001}}
        self.assertEqual(calculate_magnitude(statistics)[1], 'Major Improvement')

        statistics = {'previous': {'mean': 1}, 'next': {'mean': np.e**.5}}
        self.assertEqual(calculate_magnitude(statistics)[1], 'Moderate Improvement')

        statistics = {'previous': {'mean': 1}, 'next': {'mean': np.e**.2 + 0.0000001}}
        self.assertEqual(calculate_magnitude(statistics)[1], 'Moderate Improvement')

        statistics = {'previous': {'mean': 1}, 'next': {'mean': np.e**.2}}
        self.assertEqual(calculate_magnitude(statistics)[1], 'Minor Improvement')

        statistics = {'previous': {'mean': 1}, 'next': {'mean': 1}}
        self.assertEqual(calculate_magnitude(statistics)[1], 'Minor Improvement')
