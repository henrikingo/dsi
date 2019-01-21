"""
Unit tests for signal_processing/outliers/detection.py
"""
# pylint: disable=missing-docstring
from __future__ import print_function
import unittest

from mock import MagicMock, patch

from signal_processing.outliers.detection import run_outlier_detection, OutlierDetectionResult, \
    print_outliers
from signal_processing.outliers.gesd import GesdResult

NS = 'signal_processing.outliers.detection'


def ns(relative_name):  # pylint: disable=invalid-name
    """Return a full name from a name relative to the tested module's name space."""
    return NS + '.' + relative_name


class TestRunOutlierDetection(unittest.TestCase):
    """Test the run_outlier_detection function."""

    @patch(ns('gesd'))
    def test_series_with_one_point(self, mock_gesd):
        full_series = MagicMock()
        start = 1
        end = 2
        series = [1.0]
        max_outliers = 1
        mad = True
        significance_level = 0.05
        test_identifier = {
            'project': 'PROJECT',
            'variant': 'variant',
            'task': 'task',
            'test': 'test',
            'thread_level': 'thread_level'
        }

        res = run_outlier_detection(full_series, start, end, series, test_identifier, max_outliers,
                                    mad, significance_level)
        mock_gesd.assert_not_called()
        self.assertEqual("PROJECT variant task test thread_level", res.identifier)
        self.assertEqual(full_series, res.full_series)
        self.assertEqual(start, res.start)
        self.assertEqual(end, res.end)
        self.assertEqual(series, res.series)
        self.assertEqual(mad, res.mad)
        self.assertEqual(significance_level, res.significance_level)
        self.assertEqual(0, res.num_outliers)
        self.assertIsNone(res.gesd_result)
        self.assertIsNone(res.adjusted_indexes)

    @patch(ns('gesd'), autospec=True)
    def test_series_with_points(self, mock_gesd):
        full_series = MagicMock()
        start = 1
        end = 3
        series = [1.0, 2.0]
        max_outliers = 1
        mad = True
        significance_level = 0.05
        test_identifier = {
            'project': 'PROJECT',
            'variant': 'variant',
            'task': 'task',
            'test': 'test',
            'thread_level': 'thread_level'
        }
        suspicious_indexes = [1]

        mock_gesd.return_value.suspicious_indexes = suspicious_indexes

        res = run_outlier_detection(full_series, start, end, series, test_identifier, max_outliers,
                                    mad, significance_level)

        mock_gesd.assert_called_once_with(
            series, max_outliers, significance_level=significance_level, mad=mad)
        self.assertEqual("PROJECT variant task test thread_level", res.identifier)
        self.assertEqual(full_series, res.full_series)
        self.assertEqual(start, res.start)
        self.assertEqual(end, res.end)
        self.assertEqual(series, res.series)
        self.assertEqual(mad, res.mad)
        self.assertEqual(significance_level, res.significance_level)
        self.assertEqual(max_outliers, res.num_outliers)
        self.assertEqual(mock_gesd.return_value, res.gesd_result)
        self.assertEquals([2], res.adjusted_indexes)


class TestPrintOutliers(unittest.TestCase):
    """ Test the print_outliers function. """

    def test_does_not_crash(self):
        full_series = MagicMock()
        detection_result = OutlierDetectionResult(
            "tid", full_series, 0, 1, [1.0, 2.0], True, 0.05, 10,
            GesdResult(1, [1], [5.0], [5.0], [(1.0, 1.0)]), [1])

        lines = print_outliers(detection_result)
        self.assertIsNotNone(lines)


class TestTIG1372(unittest.TestCase):
    """ Test the print_outliers function. """

    def test_does_not_crash(self):

        detection_result = OutlierDetectionResult(
            'sys-perf linux-shard-lite change_streams_throughput 15_5c_insert 20', {
                'task': 'change_streams_throughput',
                'series': [4924.25984525373],
                'thread_level': '20',
                'variant': 'linux-shard-lite',
                'project': 'sys-perf',
                'task_ids': ['sys_perfbad5afd612e8fc917fb035d8333cffd7d68a37cc_18_05_23_22_26_42'],
                'version_ids': ['sys_perf_bad5afd612e8fc917fb035d8333cffd7d68a37cc'],
                'create_times': ['2018-05-23T22:26:42Z'],
                'test': '15_5c_insert',
                'revisions': ['bad5afd612e8fc917fb035d8333cffd7d68a37cc'],
                'orders': [12365],
                'size': 1
            },
            start=0,
            end=1,
            series=[4924.25984525373],
            mad=False,
            significance_level=0.05,
            num_outliers=0,
            gesd_result=None,
            adjusted_indexes=None)
        lines = print_outliers(detection_result)
        self.assertIsNotNone(lines)