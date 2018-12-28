"""
Unit tests for signal_processing/commands/change_points/mark.py.
"""
import unittest

from bin.common.log import setup_logging
from mock import MagicMock, call

from signal_processing.commands.change_points.mark import mark_change_points

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

    def test_update(self):
        """ Test mark."""
        mock_find = MagicMock(
            name='find',
            return_value=[{
                '_id': 1,
                'first': 'point',
                'suspect_revision': 'suspect_revision 1',
                'project': 'project 1',
                'variant': 'variant 1',
                'task': 'task 1',
                'test': 'test 1',
                'thread_level': 'thread_level 1'
            }, {
                '_id': 2,
                'second': 'point',
                'suspect_revision': 'suspect_revision 2',
                'project': 'project 2',
                'variant': 'variant 2',
                'task': 'task 2',
                'test': 'test 2',
                'thread_level': 'thread_level 2'
            }])
        mock_update = MagicMock(name='update')

        mock_processed_change_points = MagicMock(name='processed_change_points', update=mock_update)
        mock_change_points = MagicMock(name='change_points', find=mock_find)

        query = {'find': 'me'}
        mock_config = MagicMock(
            name='config',
            processed_change_points=mock_processed_change_points,
            change_points=mock_change_points,
            dry_run=False)

        mark_change_points('type', query, [], mock_config)

        mock_find.assert_called_with(query)
        mock_update.assert_has_calls([
            call(
                {
                    'task': 'task 1',
                    'thread_level': 'thread_level 1',
                    'variant': 'variant 1',
                    'project': 'project 1',
                    'test': 'test 1',
                    'suspect_revision': 'suspect_revision 1'
                }, {
                    '$set': {
                        'project': 'project 1',
                        'task': 'task 1',
                        'thread_level': 'thread_level 1',
                        'test': 'test 1',
                        'suspect_revision': 'suspect_revision 1',
                        'variant': 'variant 1',
                        'processed_type': 'type',
                        'first': 'point'
                    }
                },
                upsert=True),
            call(
                {
                    'task': 'task 2',
                    'thread_level': 'thread_level 2',
                    'variant': 'variant 2',
                    'project': 'project 2',
                    'test': 'test 2',
                    'suspect_revision': 'suspect_revision 2'
                }, {
                    '$set': {
                        'project': 'project 2',
                        'second': 'point',
                        'task': 'task 2',
                        'thread_level': 'thread_level 2',
                        'test': 'test 2',
                        'suspect_revision': 'suspect_revision 2',
                        'variant': 'variant 2',
                        'processed_type': 'type'
                    }
                },
                upsert=True)
        ])
