"""
Unit tests for signal_processing/list.py.
"""
import unittest

from bin.common.log import setup_logging
from mock import MagicMock

from signal_processing.commands.list import list_change_points

setup_logging(False)


class TestListChangePoints(unittest.TestCase):
    """
    Test suite for list_change_points method.
    """

    def test_list_processed_change_points(self):
        """ Test list processed."""
        mock_find = MagicMock(name='find', return_value=[{}])
        mock_processed_change_points = MagicMock(name='processed_change_points', find=mock_find)
        mock_change_points = MagicMock(name='change_points')

        query = {'find': 'me'}
        mock_config = MagicMock(
            name='config',
            processed_change_points=mock_processed_change_points,
            change_points=mock_change_points)

        list_change_points(True, query, [], mock_config)

        mock_find.assert_called_with(query)
        mock_change_points.find.assert_not_called()

    def test_list_change_points(self):
        """ Test list unprocessed."""
        mock_find = MagicMock(name='find', return_value=[{}])
        mock_processed_change_points = MagicMock(name='processed_change_points')
        mock_change_points = MagicMock(name='change_points', find=mock_find)

        query = {'find': 'me'}
        mock_config = MagicMock(
            name='config',
            processed_change_points=mock_processed_change_points,
            change_points=mock_change_points)

        list_change_points(False, query, [], mock_config)

        mock_find.assert_called_with(query)
        mock_processed_change_points.find.assert_not_called()
