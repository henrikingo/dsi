"""
Unit tests for signal_processing/mark.py.
"""
import unittest

from bin.common.log import setup_logging
from mock import MagicMock, call

from signal_processing.commands.mark import mark_change_points

setup_logging(False)


class TestMarkChangePoints(unittest.TestCase):
    """
    Test suite for mark_change_points.
    """

    def test_dry_run(self):
        """ Test dry run."""
        mock_find = MagicMock(
            name='find', return_value=[{
                '_id': 1,
                'first': 'point'
            }, {
                '_id': 2,
                'second': 'point'
            }])
        mock_insert = MagicMock(name='insert')

        mock_processed_change_points = MagicMock(name='processed_change_points', insert=mock_insert)
        mock_change_points = MagicMock(name='change_points', find=mock_find)

        query = {'find': 'me'}
        mock_config = MagicMock(
            name='config',
            processed_change_points=mock_processed_change_points,
            change_points=mock_change_points,
            dry_run=True)

        mark_change_points('type', query, [], mock_config)

        mock_find.assert_called_with(query)
        mock_insert.assert_not_called()

    def test_insert(self):
        """ Test mark."""
        mock_find = MagicMock(
            name='find', return_value=[{
                '_id': 1,
                'first': 'point'
            }, {
                '_id': 2,
                'second': 'point'
            }])
        mock_insert = MagicMock(name='insert')

        mock_processed_change_points = MagicMock(name='processed_change_points', insert=mock_insert)
        mock_change_points = MagicMock(name='change_points', find=mock_find)

        query = {'find': 'me'}
        mock_config = MagicMock(
            name='config',
            processed_change_points=mock_processed_change_points,
            change_points=mock_change_points,
            dry_run=False)

        mark_change_points('type', query, [], mock_config)

        mock_find.assert_called_with(query)
        mock_insert.assert_has_calls([
            call({
                'processed_type': 'type',
                'first': 'point'
            }),
            call({
                'processed_type': 'type',
                'second': 'point'
            })
        ])
