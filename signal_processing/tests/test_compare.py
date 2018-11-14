"""
Unit tests for signal_processing/compare.py.
"""
import unittest

from bin.common.log import setup_logging
from mock import patch, MagicMock, mock

# pylint: disable=invalid-name
from signal_processing.commands.compare import compare, best_fit, print_result
from signal_processing.qhat import DEFAULT_WEIGHTING

setup_logging(False)


class TestCompare(unittest.TestCase):
    """
    Test suite for compare.
    """

    @patch('signal_processing.commands.compare.PointsModel', autospec=True)
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
        compare(test_identifier, mock_config, weighting=DEFAULT_WEIGHTING)


class TestBestFit(unittest.TestCase):
    """
    Test suite for best fit method.
    """

    def test_best_fit(self):
        """ Test best fit."""
        slope, intercept = best_fit([0, 1, 2, 3, 4], [0, 1, 2, 3, 4])
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
        with mock.patch('signal_processing.commands.compare.print'):
            print_result(result, mock_config)
