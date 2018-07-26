"""
Unit tests for signal_processing/update.py.
"""
import unittest

from bin.common.log import setup_logging
from mock import MagicMock, call

from signal_processing.commands.update import update_change_points

setup_logging(False)


class TestUpdateChangePoints(unittest.TestCase):
    """
    Test suite for update_change_points.
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
        mock_update_one = MagicMock(name='update_one')

        mock_processed_change_points = MagicMock(
            name='processed_change_points', update_one=mock_update_one, find=mock_find)

        query = {'find': 'me'}
        mock_config = MagicMock(
            name='config', processed_change_points=mock_processed_change_points, dry_run=True)

        update_change_points('type', query, [], mock_config)

        mock_find.assert_called_with(query)
        mock_update_one.assert_not_called()

    def test_update(self):
        """ Test update."""
        mock_find = MagicMock(
            name='find', return_value=[{
                '_id': 1,
                'first': 'point'
            }, {
                '_id': 2,
                'second': 'point'
            }])
        mock_update_one = MagicMock(name='update_one')

        mock_processed_change_points = MagicMock(
            name='processed_change_points', update_one=mock_update_one, find=mock_find)

        query = {'find': 'me'}
        mock_config = MagicMock(
            name='config', processed_change_points=mock_processed_change_points, dry_run=False)

        update_change_points('type', query, [], mock_config)

        mock_find.assert_called_with(query)
        mock_update_one.assert_has_calls([
            call({
                '_id': 1
            }, {
                '$set': {
                    'processed_type': 'type'
                }
            }),
            call({
                '_id': 2
            }, {
                '$set': {
                    'processed_type': 'type'
                }
            })
        ])
