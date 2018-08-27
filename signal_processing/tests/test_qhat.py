"""
QHat related tests.
"""
import os
import types
import unittest

import numpy as np
from mock import patch

from bin.common.log import setup_logging
from test_lib import math_utils
from test_lib.fixture_files import FixtureFiles
from signal_processing.qhat import QHat, link_ordered_change_points, \
    get_location, generate_pairs, describe_change_point, \
    LOCATION_AHEAD, LOCATION_BEHIND, exponential_weights, DEFAULT_WEIGHTING

setup_logging(False)

FIXTURE_FILES = FixtureFiles(os.path.dirname(__file__))


class TestPostRunCheck(unittest.TestCase):
    """
    Test post run check.
    """
    NUMBER_TYPES = (types.IntType, types.LongType, types.FloatType, types.ComplexType)

    @patch('signal_processing.qhat.get_githashes_in_range_repo')
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
        algo = QHat(state, pvalue, permutations)
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
                'name': 'qhat',
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
                'name': 'qhat',
                'index': 20,
                'window_size': 40,
                'value_to_avg': 16.5,
                'average_diff': 42.9325,
                'average': 54.1,
                'value': 893.6,
                'value_to_avg_diff': 20.8,
                'probability': 0.0,
            }), math_utils.approx_dict(points[1]['algorithm']))

    @patch('signal_processing.qhat.get_githashes_in_range_repo')
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
        algo = QHat(state, pvalue, permutations)
        points = algo.change_points
        self.assertEqual(1, len(points))
        self.assertDictContainsSubset({
            'probability': 1.0,
            'suspect_revision': 'ba',
            'create_time': 16,
            'thread_level': 4,
            'order': 16,
        }, math_utils.approx_dict(points[0]))

    @patch('signal_processing.qhat.get_githashes_in_range_repo')
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
        algo = QHat(state, pvalue, permutations)
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

    @patch('signal_processing.qhat.get_githashes_in_range_repo')
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
        algo = QHat(state, pvalue, permutations)
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

    @patch('signal_processing.qhat.get_githashes_in_range_repo')
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
        algo = QHat(state, pvalue, permutations)
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
                'name': 'qhat',
                'index': 15,
                'window_size': 30,
                'value_to_avg': 7.9,
                'average_diff': 24.9,
                'average': 76.7,
                'value': 606.7,
                'value_to_avg_diff': 24.4,
                'probability': 0.0,
            }), math_utils.approx_dict(points[0]['algorithm']))

    @patch('signal_processing.qhat.get_githashes_in_range_repo')
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
        algo = QHat(state, pvalue, permutations)
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
                'name': 'qhat',
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
                'suspect_revision': 'cb',
                'create_time': 32,
                'thread_level': 4,
                'order': 32,
                'order_of_change_point': 0
            }), math_utils.approx_dict(points[1]))
        self.assertDictContainsSubset(
            math_utils.approx_dict({
                'name': 'qhat',
                'index': 33,
                'window_size': 45,
                'value_to_avg': 3.0,
                'average_diff': 23.5,
                'average': 68.9,
                'value': 206.1,
                'value_to_avg_diff': 8.8,
                'probability': 0.0,
            }), math_utils.approx_dict(points[1]['algorithm']))

    @patch('signal_processing.qhat.get_githashes_in_range_repo')
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
        algo = QHat(state, pvalue, permutations)
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
                'name': 'qhat',
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
                'name': 'qhat',
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
        algo = QHat(state, pvalue, permutations)
        points = algo.change_points
        self.assertEqual(0, len(points))


class TestLinkChangePoints(unittest.TestCase):
    """
    Test Linking the change points.
    """

    def test_empty(self):  # pylint: disable=no-self-use
        """
        Test empty.
        """
        link_ordered_change_points([], range(0))
        link_ordered_change_points(None, range(0))

    def _test_link(self, expected_points, actual_points, length):
        link_ordered_change_points(actual_points, range(length))
        for expected, change_point in zip(expected_points, actual_points):
            self.assertDictContainsSubset(expected, change_point)

    def test_middle(self):
        """
        Test single change point in middle of list.
        """
        pos = 50
        change_points = [{'start': pos, 'end': pos + 1}]
        length = pos * 2

        expected = [{'previous': 0, 'start': pos, 'end': pos + 1, 'next': length}]
        self._test_link(expected, change_points, length)

    def test_start(self):
        """
        Test single change point at start of list.
        """
        pos = 0
        change_points = [{'start': pos, 'end': pos + 1}]
        length = 100
        expected = [{'previous': 0, 'start': pos, 'end': pos + 1, 'next': length}]
        self._test_link(expected, change_points, length)

    def test_end(self):
        """
        Test single change point at end of list.
        """
        pos = 0
        change_points = [{'start': pos, 'end': pos + 1}]
        length = 100

        expected = [{'previous': 0, 'start': pos, 'end': pos + 1, 'next': length}]

        self._test_link(expected, change_points, length)

    def test_2_list(self):
        """
        Test values are correct for list.
        """
        length = 130
        change_points = [{'start': 15, 'end': 16}, {'start': 101, 'end': 102}]
        expected = [{
            'previous': 0,
            'start': 15,
            'end': 16,
            'next': 101
        }, {
            'previous': 16,
            'start': 101,
            'end': 102,
            'next': length
        }]
        self._test_link(expected, change_points, length)

    def test_3_list(self):
        """
        Test order is preserved and values are correct.
        """
        length = 130
        change_points = [{
            'start': 15,
            'end': 16
        }, {
            'start': 50,
            'end': 51
        }, {
            'start': 101,
            'end': 102
        }]
        expected = [{
            'previous': 0,
            'start': 15,
            'end': 16,
            'next': 50
        }, {
            'previous': 16,
            'start': 50,
            'end': 51,
            'next': 101
        }, {
            'previous': 51,
            'start': 101,
            'end': 102,
            'next': length
        }]
        self._test_link(expected, change_points, length)


class TestLocation(unittest.TestCase):
    """
    Test calculating the location.
    """

    def _test_location(self, filename):
        """
        Helper for location.
        """
        fixture = FIXTURE_FILES.load_json_file(os.path.join('qhat', filename))
        series = fixture['series']
        tests = fixture['test_data']

        for test_data in tests:
            change_point = test_data["change_point"]
            expected = test_data["expected"]
            series = np.abs(series, dtype=np.float64)
            prev_index = change_point['prev_index']
            index = change_point['index']
            next_index = change_point['next_index']

            before_mean = np.mean(series[prev_index:index])
            after_mean = np.mean(series[index + 1:next_index])

            location = get_location(before_mean, series[index], after_mean)

            self.assertEqual(expected['location'], location)

    def test_behind(self):
        """
        Test get location behind.
        """
        self.assertEqual(LOCATION_BEHIND, get_location(1, 9, 10))

    def test_behind1(self):
        """
        Test another get location behind.
        """
        self.assertEqual(LOCATION_BEHIND, get_location(10, 2, 1))

    def test_step_fowards(self):
        """
        Test location ahead.
        """
        self.assertEqual(LOCATION_AHEAD, get_location(10, 9, 1))

    def test_step_forwrds1(self):
        """
        Test another location ahead.
        """
        self.assertEqual(LOCATION_AHEAD, get_location(1, 2, 10))

    def test_canary_client_cpuloop_1(self):
        """
        Test canary_client_cpuloop 1 thread.
        """
        filename = 'sys-perf/linux-1-node-replSet/bestbuy_agg/canary_server-cpuloop-10x-1.json'
        self._test_location(filename)

    def test_canary_client_cpuloop_max(self):
        """
        Test canary_client_cpuloop max ops / sec.
        """
        filename = 'sys-perf/linux-1-node-replSet/bestbuy_agg/canary_server-cpuloop-10x-16.json'
        self._test_location(filename)

    def test_latency_change_15(self):
        """
        Test latency_change 15.
        """
        filename = 'sys-perf/linux-1-node-replSet/change_streams_latency/15_lookup_1c_avg_latency.json'
        self._test_location(filename)

    def test_change_streams_latency_105(self):
        """
        Test change_streams_latency 105.
        """

        filename = 'sys-perf/linux-1-node-replSet/change_streams_latency/105_1c_avg_latency.json'
        self._test_location(filename)

    def test_best_buy_agg_count(self):
        """
        Test bestbuy_agg count.
        """
        filename = 'sys-perf/linux-1-node-replSet/bestbuy_agg/count_with_type_predicate-useAgg.json'
        self._test_location(filename)

    # pylint: disable=invalid-name
    def test_bestbuy_query_count_with_and_predicate_noAgg(self):
        """
        Test bestbuy_query count_with_and_predicate_noAgg.
        """
        filename = 'sys-perf/linux-1-node-replSet/bestbuy_query/count_with_and_predicate-noAgg.json'
        self._test_location(filename)

    def test_bestbuy_agg_canary_server_sleep_10ms(self):
        """
        Test bestbuy_agg canary_server_sleep_10ms.
        """
        filename = 'sys-perf/linux-1-node-replSet/bestbuy_agg/canary_server-sleep-10ms.json'
        self._test_location(filename)

    # pylint: disable=invalid-name
    def test_bestbuy_agg_count_no_predicate_useAgg(self):
        """
        Test bestbuy_agg count_no_predicate_useAgg.
        """
        filename = 'sys-perf/linux-1-node-replSet/bestbuy_agg/count_no_predicate-useAgg.json'
        self._test_location(filename)


class TestGeneratePairs(unittest.TestCase):
    """
    Test generate pairs.
    """

    def test_empty(self):
        """
        Test empty array.
        """
        self.assertEqual(list(generate_pairs(None)), [])
        self.assertEqual(list(generate_pairs([])), [])

    def test_single(self):
        """
        Test single element array.
        """
        self.assertEqual(list(generate_pairs([1])), [])

    def test_even(self):
        """
        Test even array length.
        """
        self.assertEqual(list(generate_pairs([1, 2])), [(1, 2)])

    def test_odd(self):
        """
        Test odd array length.
        """
        self.assertEqual(list(generate_pairs([1, 2, 3])), [(1, 2), (2, 3)])


class TestDescribeChangePoints(unittest.TestCase):
    """
    Test describe change points.
    """

    def test_empty(self):
        """
        Test empty array.
        """
        expected = {}
        change_point = {'previous': 0, 'start': 0, 'end': 0, 'next': 0}

        description = describe_change_point(change_point, range(0), {})
        self.assertEqual(description, expected)

    def test_start_empty(self):
        """
        Test start empty.
        """
        expected = {'next': dict(nobs=1, minmax=(0, 0), mean=0.0, skewness=0.0, kurtosis=-3.0)}
        change_point = {'previous': 0, 'start': 0, 'end': 0, 'next': 1}

        description = describe_change_point(change_point, range(1), {})
        self.assertEqual(len(expected), len(description))
        to_next = description['next']
        self.assertDictContainsSubset(expected['next'], to_next)
        self.assertTrue(np.isnan(to_next['variance']))

    def test_end_empty(self):
        """
        Test end empty array.
        """
        expected = {'previous': dict(nobs=1, minmax=(0, 0), mean=0.0, skewness=0.0, kurtosis=-3.0)}
        change_point = {'previous': 0, 'start': 1, 'end': 1, 'next': 1}

        description = describe_change_point(change_point, range(1), {})
        self.assertEqual(len(expected), len(description))
        from_previous = description['previous']
        self.assertDictContainsSubset(expected['previous'], from_previous)
        self.assertTrue(np.isnan(from_previous['variance']))

    def test_start_and_end_1(self):
        """
        Test with start and end.
        """
        expected = {
            'previous': dict(nobs=1, minmax=(0, 0), mean=0.0, skewness=0.0, kurtosis=-3.0),
            'next': dict(nobs=1, minmax=(1, 1), mean=1.0, skewness=0.0, kurtosis=-3.0)
        }
        change_point = {'previous': 0, 'start': 1, 'end': 1, 'next': 2}

        description = describe_change_point(change_point, range(2), {})
        self.assertEqual(len(expected), len(description))
        from_previous = description['previous']
        self.assertDictContainsSubset(expected['previous'], from_previous)
        self.assertTrue(np.isnan(from_previous['variance']))

        to_next = description['next']
        self.assertDictContainsSubset(expected['next'], to_next)
        self.assertTrue(np.isnan(to_next['variance']))

    def test_start_and_end_2(self):
        """
        Test another start and end.
        """
        expected = {
            'previous': dict(nobs=1, minmax=(0, 0), mean=0.0, skewness=0.0, kurtosis=-3.0),
            'next': dict(nobs=1, minmax=(2, 2), mean=2.0, skewness=0.0, kurtosis=-3.0)
        }
        change_point = {'previous': 0, 'start': 1, 'end': 2, 'next': 3}

        description = describe_change_point(change_point, range(3), {})
        self.assertEqual(len(expected), len(description))
        from_previous = description['previous']
        self.assertDictContainsSubset(expected['previous'], from_previous)
        self.assertTrue(np.isnan(from_previous['variance']))

        to_next = description['next']
        self.assertDictContainsSubset(expected['next'], to_next)
        self.assertTrue(np.isnan(to_next['variance']))

    def test_start_and_end_3(self):
        """
        Test yet another start end.
        """
        expected = {
            'previous':
                dict(nobs=5, minmax=(0, 4), mean=2.0, variance=2.5, skewness=0.0, kurtosis=-1.3),
            'next':
                dict(nobs=9, minmax=(6, 14), mean=10.0, variance=7.5, skewness=0.0, kurtosis=-1.23)
        }
        change_point = {'previous': 0, 'start': 5, 'end': 6, 'next': 15}

        description = describe_change_point(change_point, range(15), {})
        self.assertEqual(len(expected), len(description))
        from_previous = description['previous']
        self.assertDictContainsSubset(
            math_utils.approx_dict(expected['previous']), math_utils.approx_dict(from_previous))

        to_next = description['next']
        self.assertDictContainsSubset(
            math_utils.approx_dict(expected['next']), math_utils.approx_dict(to_next))


class TestExponentialWeights(unittest.TestCase):
    """
    Test exponential_weights.
    """

    def test_exponential_weights_default(self):
        """
        Test yet another start end.
        """
        expected = [
            1, 0.5506, 0.30316, 0.16692, 0.09191, 0.0506, 0.02786, 0.01534, 0.00845, 0.00465
        ]
        weights = exponential_weights(100, DEFAULT_WEIGHTING)
        self.assertTrue(np.allclose(expected, weights, rtol=1e-02))

    def test_exponential_weights_1tenth(self):
        """
        Test yet another start end.
        """
        expected = [
            1, 0.43634, 0.19039, 0.08308, 0.03625, 0.01582, 0.0069, 0.00301, 0.00131, 0.00057
        ]
        weights = exponential_weights(100, DEFAULT_WEIGHTING / 10)
        self.assertTrue(np.allclose(expected, weights, rtol=1e-02))

    def test_exponential_weights_x10(self):
        """
        Test yet another start end.
        """
        expected = [
            1, 0.69478, 0.48272, 0.33539, 0.23302, 0.1619, 0.11248, 0.07815, 0.0543, 0.03773
        ]

        weights = exponential_weights(100, DEFAULT_WEIGHTING * 10)
        self.assertTrue(np.allclose(expected, weights, rtol=1e-02))

    def test_exponential_weights_x100(self):
        """
        Test yet another start end.
        """
        expected = [1, 0.87671, 0.76863, 0.67387, 0.59079, 0.51795, 0.4541, 0.39811, 0.34903, 0.306]

        weights = exponential_weights(100, DEFAULT_WEIGHTING * 100)
        self.assertTrue(np.allclose(expected, weights, rtol=1e-02))

    def test_exponential_weights_size_200(self):
        """
        Test yet another start end.
        """
        expected = [
            1, 0.5506, 0.30316, 0.16692, 0.09191, 0.0506, 0.02786, 0.01534, 0.00845, 0.00465
        ]

        weights = exponential_weights(200, DEFAULT_WEIGHTING)
        np.set_printoptions(precision=5, suppress=True)
        print weights
        self.assertTrue(np.allclose(expected, weights, rtol=1e-02))
