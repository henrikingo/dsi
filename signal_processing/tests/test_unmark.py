"""
Unit tests for signal_processing/mark.py.
"""
import unittest

from bin.common.log import setup_logging
from mock import MagicMock, call

from signal_processing.commands.unmark import unmark_change_points

setup_logging(False)


class TestUnmarkChangePoints(unittest.TestCase):
    """
    Test suite for unmark_change_points.
    """

    def _test_dry_run(self, expected, processed_type='type'):
        """ Test dry run."""
        mock_find = MagicMock(
            name='find', return_value=[{
                '_id': 1,
                'first': 'point'
            }, {
                '_id': 2,
                'second': 'point'
            }])
        mock_remove = MagicMock(name='remove')

        mock_processed_change_points = MagicMock(
            name='processed_change_points', remove=mock_remove, find=mock_find)

        query = {'find': 'me'}
        mock_config = MagicMock(
            name='config', processed_change_points=mock_processed_change_points, dry_run=True)

        unmark_change_points(processed_type, query, [], mock_config)
        mock_find.assert_called_with(expected)
        mock_remove.assert_not_called()

    def test_dry_run(self):
        """ Test dry run."""

        self._test_dry_run({'find': 'me', 'processed_type': 'type'})

    def test_dry_run_all(self):
        """ Test dry run no processed type."""

        self._test_dry_run({'find': 'me'}, processed_type=None)

    def test_unmark(self):
        """ Test dry run."""
        mock_find = MagicMock(
            name='find', return_value=[{
                '_id': 1,
                'first': 'point'
            }, {
                '_id': 2,
                'second': 'point'
            }])
        mock_remove = MagicMock(name='remove')

        mock_processed_change_points = MagicMock(
            name='processed_change_points', remove=mock_remove, find=mock_find)

        query = {'find': 'me'}
        mock_config = MagicMock(
            name='config', processed_change_points=mock_processed_change_points, dry_run=False)
        processed_type = None
        expected = query
        unmark_change_points(processed_type, query, [], mock_config)
        mock_find.assert_called_with(expected)
        calls = [call({'_id': 1}), call({'_id': 2})]
        mock_remove.assert_has_calls(calls)
