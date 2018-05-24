import types
import unittest
from signal_processing.qhat import QHat


class TestPostRunCheck(unittest.TestCase):

    NUMBER_TYPES = (types.IntType, types.LongType, types.FloatType, types.ComplexType)

    def assert_cp_equal(self, expect, actual):
        keys = {
            'average', 'average_diff', 'index', 'order_of_changepoint', 'probability', 'revision',
            'value', 'value_to_avg', 'value_to_avg_diff', 'window_size', 'order'
        }
        errors = []
        for key in keys:
            expect_v = expect[key]
            actual_v = actual[key]
            # use '\s#.*$' as regex to trim error message to something you can use as expected
            msg = "'{}': {}, # expect={}".format(key, actual_v, expect_v)
            try:
                if isinstance(expect_v, basestring):
                    if expect_v != actual_v:
                        errors.append(msg)
                else:
                    self.assertTrue(
                        isinstance(expect_v, TestPostRunCheck.NUMBER_TYPES),
                        "Expect {}={} is number".format(key, expect_v))
                    self.assertTrue(
                        isinstance(actual_v, TestPostRunCheck.NUMBER_TYPES),
                        "Actual {}={} is number".format(key, actual_v))
                    self.assertAlmostEquals(expect[key], actual[key], None, msg, 0.01)
            except AssertionError as e:
                errors.append(e.message)
        self.assertEqual(len(expect), len(actual))
        self.assertEqual([], errors, "\n".join(errors) + "\n\n")

    def test_random_ish_data(self):
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
            ]
        }
        pvalue = 0.01
        permutations = 100
        online = 20
        threshold = None
        algo = QHat(state, pvalue, permutations, online, threshold)
        points = algo.change_points
        self.assertEqual(2, len(points))
        self.assert_cp_equal({
            'algorithm': 'qhat',
            'index': 40,
            'window_size': 60,
            'value_to_avg': 23.8522717629,
            'average_diff': 88.7766666667,
            'average': 103.366666667,
            'value': 2465.52982456,
            'value_to_avg_diff': 27.772273021,
            'revision': 'ca',
            'order_of_changepoint': 0,
            'probability': 0.0,
            'order': 41
        }, points[0])
        self.assert_cp_equal({
            'algorithm': 'qhat',
            'index': 20,
            'window_size': 40,
            'value_to_avg': 15.6853779551,
            'order_of_changepoint': 1,
            'average_diff': 42.9325,
            'average': 54.1,
            'value': 848.578947368,
            'value_to_avg_diff': 19.7654212396,
            'revision': 'ba',
            'probability': 0.0,
            'order': 21
        }, points[1])

    def test_finds_simple_regression(self):
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
            ]
        }
        pvalue = 0.01
        permutations = 100
        online = 20
        threshold = None
        algo = QHat(state, pvalue, permutations, online, threshold)
        points = algo.change_points
        self.assertEqual(1, len(points))
        self.assert_cp_equal({
            'algorithm': 'qhat',
            'average': 75.0,
            'average_diff': 25.0,
            'index': 15,
            'order_of_changepoint': 0,
            'probability': 0.0,
            'revision': 'ba',
            'value': 650.0,
            'value_to_avg': 8.67,
            'value_to_avg_diff': 26.0,
            'window_size': 30,
            'order': 16
        }, points[0])

    def test_finds_simple_regression2(self):
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
            ]
        }
        pvalue = 0.01
        permutations = 100
        online = 20
        threshold = None
        algo = QHat(state, pvalue, permutations, online, threshold)
        points = algo.change_points
        self.assertEqual(1, len(points))
        self.assert_cp_equal({
            'algorithm': 'qhat',
            'average': 76.67,
            'average_diff': 24.89,
            'index': 15,
            'order_of_changepoint': 0,
            'probability': 0.0,
            'revision': 'ba',
            'value': 566.67,
            'value_to_avg': 7.39,
            'value_to_avg_diff': 22.76,
            'window_size': 30,
            'order': 16
        }, points[0])

    def test_regression_and_recovery(self):
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
            ]
        }
        pvalue = 0.01
        permutations = 100
        online = 20
        threshold = None
        algo = QHat(state, pvalue, permutations, online, threshold)
        points = sorted(algo.change_points, key=lambda i: i['index'])
        self.assertEqual(2, len(points))
        self.assert_cp_equal({
            'algorithm': 'qhat',
            'value_to_avg': 2.77196885428,
            'average_diff': 23.5061728395,
            'average': 68.8888888889,
            'value': 190.957854406,
            'value_to_avg_diff': 8.12373225152,
            'window_size': 45,
            'index': 15,
            'order_of_changepoint': 0,
            'probability': 0.0,
            'revision': 'ba',
            'order': 16
        }, points[0])
        self.assert_cp_equal({
            'algorithm': 'qhat',
            'value_to_avg': 7.34782608696,
            'average_diff': 24.8888888889,
            'average': 76.6666666667,
            'value': 563.333333333,
            'value_to_avg_diff': 22.6339285714,
            'index': 30,
            'window_size': 30,
            'order_of_changepoint': 1,
            'probability': 0.0,
            'revision': 'ca',
            'order': 31
        }, points[1])

    def test_two_regressions(self):
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
            ]
        }
        pvalue = 0.01
        permutations = 100
        online = 20
        threshold = None
        algo = QHat(state, pvalue, permutations, online, threshold)
        points = sorted(algo.change_points, key=lambda i: i['index'])
        self.assertEqual(2, len(points))
        self.assert_cp_equal({
            'algorithm': 'qhat',
            'value_to_avg': 10.8222811671,
            'average_diff': 43.6543209877,
            'average': 101.111111111,
            'value': 1094.25287356,
            'value_to_avg_diff': 25.0663129973,
            'window_size': 45,
            'index': 15,
            'order_of_changepoint': 0,
            'probability': 0.0,
            'revision': 'ba',
            'order': 16
        }, points[0])
        self.assert_cp_equal({
            'algorithm': 'qhat',
            'index': 30,
            'window_size': 30,
            'value_to_avg': 5.2,
            'order_of_changepoint': 1,
            'average_diff': 25.0,
            'average': 125.0,
            'value': 650.0,
            'value_to_avg_diff': 26.0,
            'probability': 0.0,
            'revision': 'ca',
            'order': 31
        }, points[1])

    def test_no_regressions(self):
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
                45
            ]
        }
        pvalue = 0.01
        permutations = 100
        online = 20
        threshold = None
        algo = QHat(state, pvalue, permutations, online, threshold)
        points = algo.change_points
        self.assertEqual(0, len(points))
