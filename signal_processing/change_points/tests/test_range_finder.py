"""
Unit tests for the signal_processing.change_points.range_finder module.
"""
import os
import unittest

import numpy as np

from signal_processing.change_points.range_finder import describe_change_point
from signal_processing.change_points.range_finder import generate_start_and_end
from signal_processing.change_points.range_finder import link_ordered_change_points
from signal_processing.change_points.range_finder import _generate_pairs
from signal_processing.change_points.range_finder import _get_location
from signal_processing.change_points.range_finder import _LOCATION_BEHIND
from signal_processing.change_points.range_finder import _LOCATION_AHEAD
from signal_processing.change_points.range_finder import _select_start_end
from signal_processing.change_points.weights import DEFAULT_WEIGHTING
from test_lib import math_utils
from test_lib.fixture_files import FixtureFiles

FIXTURE_FILES = FixtureFiles(os.path.dirname(__file__))


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
        fixture = FIXTURE_FILES.load_json_file(os.path.join('e-divisive', filename))
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

            location = _get_location(before_mean, series[index], after_mean)

            self.assertEqual(expected['location'], location)

    def test_behind(self):
        """
        Test get location behind.
        """
        self.assertEqual(_LOCATION_BEHIND, _get_location(1, 9, 10))

    def test_behind1(self):
        """
        Test another get location behind.
        """
        self.assertEqual(_LOCATION_BEHIND, _get_location(10, 2, 1))

    def test_step_fowards(self):
        """
        Test location ahead.
        """
        self.assertEqual(_LOCATION_AHEAD, _get_location(10, 9, 1))

    def test_step_forwrds1(self):
        """
        Test another location ahead.
        """
        self.assertEqual(_LOCATION_AHEAD, _get_location(1, 2, 10))

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
        self.assertEqual(list(_generate_pairs(None)), [])
        self.assertEqual(list(_generate_pairs([])), [])

    def test_single(self):
        """
        Test single element array.
        """
        self.assertEqual(list(_generate_pairs([1])), [])

    def test_even(self):
        """
        Test even array length.
        """
        self.assertEqual(list(_generate_pairs([1, 2])), [(1, 2)])

    def test_odd(self):
        """
        Test odd array length.
        """
        self.assertEqual(list(_generate_pairs([1, 2, 3])), [(1, 2), (2, 3)])


class TestStartEnd(unittest.TestCase):
    """
    Test getting the start / end for a change point.
    """

    def _test_start_end(self, filename):
        """
        Util for start end.
        """
        fixture = FIXTURE_FILES.load_json_file(os.path.join('e-divisive', filename))
        series = fixture['series']
        tests = fixture['test_data']

        for test_data in tests:
            change_point = test_data["change_point"]
            expected = test_data["expected"]

            start, end, location = _select_start_end(
                series,
                change_point['prev_index'],
                change_point['index'],
                change_point['next_index'],
                weighting=DEFAULT_WEIGHTING)
            self.assertEqual(expected['start'], start)
            self.assertEqual(expected['end'], end)
            self.assertEqual(expected['location'], location)

    def test_canary_client_cpuloop_1(self):
        """
        Test canary_client_cpuloop 1 thread.
        """
        filename = 'sys-perf/linux-1-node-replSet/bestbuy_agg/canary_server-cpuloop-10x-1.json'
        self._test_start_end(filename)

    def test_canary_client_cpuloop_16(self):
        """
        Test canary server cpuloop.
        """
        filename = 'sys-perf/linux-1-node-replSet/bestbuy_agg/canary_server-cpuloop-10x-16.json'
        self._test_start_end(filename)

    def test_latency_change_15(self):
        """
        Test change_streams_latency 15.
        """
        filename = 'sys-perf/linux-1-node-replSet/change_streams_latency/15_lookup_1c_avg_latency.json'
        self._test_start_end(filename)

    def test_change_streams_latency_105(self):
        """
        Test change_streams_latency 105.
        """
        filename = 'sys-perf/linux-1-node-replSet/change_streams_latency/105_1c_avg_latency.json'
        self._test_start_end(filename)

    def test_best_buy_agg_count(self):
        """
        Test bestbuy_agg count.
        """
        filename = 'sys-perf/linux-1-node-replSet/bestbuy_agg/count_with_type_predicate-useAgg.json'
        self._test_start_end(filename)

    # pylint: disable=invalid-name
    def test_bestbuy_query_count_with_and_predicate_noAgg(self):
        """
        Test bestbuy_query count_with_and_predicate_noAgg.
        """
        filename = 'sys-perf/linux-1-node-replSet/bestbuy_query/count_with_and_predicate-noAgg.json'
        self._test_start_end(filename)

    def test_bestbuy_agg_canary_server_sleep_10ms(self):
        """
        Test bestbuy_aggc anary_server_sleep_10ms.
        """
        filename = 'sys-perf/linux-1-node-replSet/bestbuy_agg/canary_server-sleep-10ms.json'
        self._test_start_end(filename)

    # pylint: disable=invalid-name
    def test_bestbuy_agg_count_no_predicate_useAgg(self):
        """
        Test bestbuy_agg count_no_predicate_useAgg.
        """
        filename = 'sys-perf/linux-1-node-replSet/bestbuy_agg/count_no_predicate-useAgg.json'
        self._test_start_end(filename)


class TestGenerateStartEnd(unittest.TestCase):
    """
    Test generate_start_and_end.
    """

    def setUp(self):
        self.old_err_state = np.seterr(all='raise')

    def tearDown(self):
        np.seterr(**self.old_err_state)

    def test_empty(self):
        """
        Test empty array.
        """
        self.assertEqual(list(generate_start_and_end(None, [])), [])
        self.assertEqual(list(generate_start_and_end([], [])), [])

    def test_single(self):
        """
        Test single element.
        """
        array = [5 if int(a / 5) else 10 for a in range(10)]
        expected = [{'index': 5, 'start': 4, 'end': 5, 'location': 'behind'}]

        self.assertEqual(list(generate_start_and_end([5], array)), expected)

    def test_single_at_start(self):
        """
        Test single at start of array.
        """
        array = [5 if a else 10 for a in range(10)]
        expected = [{'index': 0, 'start': 1, 'end': 2, 'location': 'ahead'}]
        self.assertEqual(list(generate_start_and_end([0], array)), expected)

    def test_single_at_end(self):
        """
        Test single at end.
        """
        array = [10 if a < 9 else 5 for a in range(11)]
        expected = [{'index': 9, 'start': 8, 'end': 9, 'location': 'behind'}]
        actual = list(generate_start_and_end([9], array))
        self.assertEqual(actual, expected)

    def test_even(self):
        """
        Test even.
        """
        expected = [{
            'index': 5,
            'start': 4,
            'end': 5,
            'location': 'behind'
        }, {
            'index': 10,
            'start': 9,
            'end': 10,
            'location': 'behind'
        }]

        array = [5 if int(a / 5) else 10 for a in range(10)] + \
                [20 for a in range(10)]
        actual = list(generate_start_and_end([5, 10], array))
        self.assertEqual(actual, expected)

    def test_odd(self):
        """
        Test odd.
        """
        array = [5 if int(a / 5) else 10 for a in range(10)] + \
                [15 if int(a / 5) else 20 for a in range(10)]
        actual = list(generate_start_and_end([5, 10, 15], array))
        self.assertEqual(actual, [{
            'start': 4,
            'index': 5,
            'end': 5,
            'location': 'behind'
        }, {
            'start': 9,
            'index': 10,
            'end': 10,
            'location': 'behind'
        }, {
            'start': 14,
            'index': 15,
            'end': 15,
            'location': 'behind'
        }])

    def test_outlier_up(self):
        """
        Test outlier up.
        """
        array = [5 for _ in range(5)] + [10] + [5 for _ in range(5)]
        expected = [{'index': 5, 'start': 5, 'end': 5, 'location': 'ahead'}]
        actual = list(generate_start_and_end([5], array))
        self.assertEqual(actual, expected)

    def test_outlier_down(self):
        """
        Test outlier down.
        """
        array = [15 for _ in range(5)] + [10] + [15 for _ in range(5)]
        expected = [{'index': 5, 'start': 5, 'end': 5, 'location': 'ahead'}]
        actual = list(generate_start_and_end([5], array))
        self.assertEqual(actual, expected)

    def test_outlier_upish(self):
        """
        Test outlier up?
        """
        array = [5 for _ in range(5)] + [4, 10, 4] + [5 for _ in range(5)]
        expected = [{'index': 7, 'start': 6, 'end': 7, 'location': 'ahead'}]
        actual = list(generate_start_and_end([7], array))
        self.assertEqual(actual, expected)

    def test_outlier_downish(self):
        """
        Test outlier down?
        """
        array = [15 for _ in range(5)] + [14, 10, 14] + [15 for _ in range(5)]
        expected = [{'index': 7, 'start': 6, 'end': 7, 'location': 'ahead'}]
        actual = list(generate_start_and_end([7], array))
        self.assertEqual(actual, expected)

    def test_exception(self):
        """
        Test raises exception.
        """
        array = [15 for _ in range(5)] + [14, 10, 19] + [15 for _ in range(5)]
        self.assertRaises(FloatingPointError, generate_start_and_end, [6, 7], array)

    def test_outlier_bounded_left(self):
        """
        Test bound left.
        """
        array = [15 for _ in range(5)] + [14, 10, 19] + [15 for _ in range(5)]
        expected = [{
            "location": "ahead",
            'end': 6,
            'index': 6,
            'start': 5
        }, {
            'location': 'behind',
            'end': 9,
            'index': 9,
            'start': 8
        }]
        actual = list(generate_start_and_end([6, 9], array))
        self.assertEqual(actual, expected)

    def test_outlier_bounded_right(self):
        """
        Test bound right.
        """
        array = [15 for _ in range(5)] + [14, 10, 20] + [15 for _ in range(5)]
        expected = [{
            "location": "ahead",
            'end': 6,
            'index': 6,
            'start': 5
        }, {
            'location': 'ahead',
            'end': 9,
            'index': 9,
            'start': 9
        }]
        actual = list(generate_start_and_end([6, 9], array))
        self.assertEqual(actual, expected)
