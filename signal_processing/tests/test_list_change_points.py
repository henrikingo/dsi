"""
Unit tests for signal_processing/list.py.
"""
import unittest

from bin.common.log import setup_logging
from mock import MagicMock

import signal_processing.commands.list_change_points as list_change_points

setup_logging(False)


class TestListChangePoints(unittest.TestCase):
    """
    Test suite for list_change_points method.
    """

    def _assert_query(self, change_point_type, query, mock_unprocessed_change_points,
                      mock_processed_change_points, mock_change_points):
        """ Helper for query assertions. """
        if change_point_type == list_change_points.CHANGE_POINT_TYPE_UNPROCESSED:
            mock_unprocessed_change_points.aggregate.assert_called_with()
        else:
            mock_unprocessed_change_points.aggregate.assert_not_called()

        if change_point_type == list_change_points.CHANGE_POINT_TYPE_PROCESSED:
            mock_processed_change_points.aggregate.assert_called_with()
        else:
            mock_processed_change_points.aggregate.assert_not_called()

        if change_point_type == list_change_points.CHANGE_POINT_TYPE_RAW:
            mock_change_points.aggregate.assert_called_with()
        else:
            mock_change_points.aggregate.assert_not_called()

    def _test_limit(self, change_point_type):
        """ test limit helper."""
        mock_cursor = MagicMock(name='cursor', return_value=[{}])
        query = {'find': 'me'}
        mock_processed_change_points = MagicMock(
            name='processed_change_points',
            find=MagicMock(name='processed find', return_value=mock_cursor))
        mock_unprocessed_change_points = MagicMock(
            name='unprocessed_change_points',
            find=MagicMock(name='unprocessed find', return_value=mock_cursor))
        mock_change_points = MagicMock(
            name='change_points', find=MagicMock(name='find', return_value=mock_cursor))

        mock_config = MagicMock(
            name='config',
            processed_change_points=mock_processed_change_points,
            unprocessed_change_points=mock_unprocessed_change_points,
            change_points=mock_change_points)
        human_readable = True
        show_canaries = False
        show_wtdevelop = False
        list_change_points.list_change_points(change_point_type, query, 100, human_readable,
                                              show_canaries, show_wtdevelop, [], mock_config)

    def _test_list_all(self, change_point_type):
        """ Test list all helper."""

        query = {'find': 'me'}
        mock_processed_change_points = MagicMock(
            name='processed_change_points',
            find=MagicMock(name='processed find', return_value=[{}]))
        mock_unprocessed_change_points = MagicMock(
            name='unprocessed_change_points',
            find=MagicMock(name='unprocessed find', return_value=[{}]))
        mock_change_points = MagicMock(
            name='change_points', find=MagicMock(name='find', return_value=[{}]))

        mock_config = MagicMock(
            name='config',
            processed_change_points=mock_processed_change_points,
            unprocessed_change_points=mock_unprocessed_change_points,
            change_points=mock_change_points)

        human_readable = True
        show_canaries = False
        show_wtdevelop = False
        list_change_points.list_change_points(change_point_type, query, None, human_readable,
                                              show_canaries, show_wtdevelop, [], mock_config)

    def test_list_all_unprocessed_change_points(self):
        """ Test list unprocessed."""
        self._test_list_all(list_change_points.CHANGE_POINT_TYPE_UNPROCESSED)

    def test_list_100_unprocessed_change_points(self):
        """ Test list unprocessed."""
        self._test_limit(list_change_points.CHANGE_POINT_TYPE_UNPROCESSED)

    def test_list_all_processed_change_points(self):
        """ Test list processed."""
        self._test_list_all(list_change_points.CHANGE_POINT_TYPE_PROCESSED)

    def test_list_100_processed_change_points(self):
        """ Test list processed."""
        self._test_limit(list_change_points.CHANGE_POINT_TYPE_PROCESSED)

    def test_list_all_change_points(self):
        """ Test list unprocessed."""
        self._test_list_all(list_change_points.CHANGE_POINT_TYPE_RAW)

    def test_list_100_change_points(self):
        """ Test list unprocessed."""
        self._test_limit(list_change_points.CHANGE_POINT_TYPE_RAW)
