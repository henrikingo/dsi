"""
Unit tests for signal_processing/change_points/compare.py.
"""
import unittest

from bin.common.log import setup_logging
from mock import patch, MagicMock

# pylint: disable=invalid-name
from signal_processing.change_points import compare
from signal_processing.change_points.weights import DEFAULT_WEIGHTING

setup_logging(False)

NS = 'signal_processing.change_points.compare'


def ns(relative_name):  # pylint: disable=invalid-name
    """Return a full name from a name relative to the tested module's name space."""
    return NS + '.' + relative_name


class TestCompare(unittest.TestCase):
    """
    Test suite for compare.
    """

    @patch(ns('PointsModel'))
    def test_attributes(self, mock_model):
        """ Test compare."""
        test_identifier = {
            'project': 'project',
            'variant': 'variant',
            'task': 'task',
            'test': 'test'
        }
        mock_config = MagicMock(name='config')
        series = {'1': [0, 1]}
        revisions = {'1': [0, 1]}
        orders = {'1': [0, 1]}
        create_times = {'1': [0, 1]}
        task_ids = {'1': [0, 1]}

        mock_model_instance = mock_model.return_value
        mock_model_instance.get_points.return_value = {
            'series': series,
            'revisions': revisions,
            'orders': orders,
            'create_times': create_times,
            'task_ids': task_ids,
        }
        compare.compare(test_identifier, 1, mock_config, weighting=DEFAULT_WEIGHTING)


class TestBestFit(unittest.TestCase):
    """
    Test suite for best fit method.
    """

    def test_best_fit(self):
        """ Test best fit."""
        slope, intercept = compare.best_fit([0, 1, 2, 3, 4], [0, 1, 2, 3, 4])
        self.assertEqual(intercept, 0.0)
        self.assertEqual(slope, 1.0)


class TestPrintResult(unittest.TestCase):
    """
    Test suite for print_result method.
    """

    def test_print_result_dry_run(self):
        """ Test print."""
        result = {
            'test': 'test',
            'series': 'series',
            'thread_level': '1',
            'revisions': [0, 1],
        }
        mock_config = MagicMock(name='config', dry_run=True)
        with patch(ns('print')):
            compare.print_result(result, mock_config)
