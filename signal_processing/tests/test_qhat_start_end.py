"""
QHat start end related tests.
"""
import os
import unittest

import numpy as np

from bin.common.log import setup_logging
from signal_processing.qhat import select_start_end, generate_start_and_end, DEFAULT_WEIGHTING
from test_lib.fixture_files import FixtureFiles

setup_logging(False)

FIXTURE_FILES = FixtureFiles(os.path.dirname(__file__))


class TestStartEnd(unittest.TestCase):
    """
    Test getting the start / end for a change point.
    """

    def _test_start_end(self, filename):
        """
        Util for start end.
        """
        fixture = FIXTURE_FILES.load_json_file(os.path.join('qhat', filename))
        series = fixture['series']
        tests = fixture['test_data']

        for test_data in tests:
            change_point = test_data["change_point"]
            expected = test_data["expected"]

            start, end, location = select_start_end(
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
