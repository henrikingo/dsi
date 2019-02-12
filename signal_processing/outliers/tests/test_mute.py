"""
Unit tests for signal_processing/outliers/mute.py.
"""
# pylint: disable=missing-docstring
from __future__ import print_function

import unittest

import pymongo
from mock import MagicMock, patch

from signal_processing.outliers.mute import get_identifier, get_mute, mute_outliers

NS = 'signal_processing.outliers.mute'


def ns(relative_name):  # pylint: disable=invalid-name
    """Return a full name from a name relative to the tested module's name space."""
    return NS + '.' + relative_name


class TestGetIdentifier(unittest.TestCase):
    """ Test get_identifier. """

    def test(self):
        """ Test get_identifier, """
        mute = {
            'revision': 'r',
            'project': 'p',
            'variant': 'v',
            'task': 'k',
            'test': 't',
            'thread_level': 'l'
        }
        self.assertDictEqual(mute, get_identifier(mute))

    def test_extra(self):
        """ Test get_identifier with extra params, """
        mute = {
            'revision': 'r',
            'project': 'p',
            'variant': 'v',
            'task': 'k',
            'test': 't',
            'thread_level': 'l'
        }
        copy_with_extra = {k: mute[k] if k in mute else k for k in mute.keys() + ['random']}
        self.assertDictEqual(mute, get_identifier(copy_with_extra))


class TestGetMute(unittest.TestCase):
    """ Test get_mute. """

    def _test(self, found=True):
        test_identifier = {
            'revision': 'r',
            'project': 'p',
            'variant': 'v',
            'task': 'k',
            'test': 't',
            'thread_level': 'l'
        }

        mock_mute_outliers_collection = MagicMock(name='mute_outliers_collection')
        mock_mute_outliers_collection \
            .find.return_value \
            .sort.return_value.limit.return_value = iter(['mute'] if found else [])
        if found:
            self.assertEquals('mute', get_mute(test_identifier, mock_mute_outliers_collection))
        else:
            self.assertIsNone(get_mute(test_identifier, mock_mute_outliers_collection))

        mock_find = mock_mute_outliers_collection.find
        mock_find.assert_called_once_with(test_identifier)
        mock_sort = mock_find.return_value.sort
        mock_sort.assert_called_once_with([('order', pymongo.DESCENDING)])

        mock_limit = mock_sort.return_value.limit

        mock_limit.assert_called_once_with(1)

    def test_found(self):
        """ Test get_mute with results. """
        self._test()

    def test_not_found(self):
        """ Test get_mute with no results. """
        self._test(found=False)


class TestMuteOutlier(unittest.TestCase):
    """ Test mute_outliers. """

    def test_nothing(self):
        """ test no mute or points. """
        with patch(ns('get_mute')) as mock_get_mute:
            mock_get_mute.return_value = None
            test_identifier = {}
            enabled = True
            mock_points = MagicMock(name='mock_points')
            mock_mute_outliers = MagicMock(name='mock_mute_outliers')
            mock_config = MagicMock(
                name='command_config', points=mock_points, mute_outliers=mock_mute_outliers)

            mock_points.find.return_value.sort.return_value.limit.return_value = iter([])

            mute_outliers(test_identifier, enabled, mock_config)

            mock_mute_outliers.update_one.assert_not_called()

    def test_with_mute(self):
        """ test with mute. """
        with patch(ns('get_mute')) as mock_get_mute:
            mock_get_mute.return_value = {'_id': 'id', 'last_updated_at': 1, 'some': 'value'}
            test_identifier = {}
            enabled = True
            mock_points = MagicMock(name='mock_points')
            mock_mute_outliers = MagicMock(name='mock_mute_outliers')
            mock_config = MagicMock(
                name='command_config',
                points=mock_points,
                mute_outliers=mock_mute_outliers,
                compact=True,
                dry_run=False)

            mock_points.find.return_value.sort.return_value.limit.return_value = iter([])

            mute_outliers(test_identifier, enabled, mock_config)

            mock_mute_outliers.update_one.assert_called_with(
                {
                    '_id': 'id'
                }, {
                    '$currentDate': {
                        'last_updated_at': True
                    },
                    '$set': {
                        '_id': 'id',
                        'some': 'value',
                        'enabled': True
                    },
                },
                upsert=True)

    def test_with_mute_dryrun(self):
        """ test dryrun with mute. """
        with patch(ns('get_mute')) as mock_get_mute:
            mock_get_mute.return_value = {'_id': 'id', 'last_updated_at': 1, 'some': 'value'}
            test_identifier = {}
            enabled = True
            mock_points = MagicMock(name='mock_points')
            mock_mute_outliers = MagicMock(name='mock_mute_outliers')
            mock_config = MagicMock(
                name='command_config',
                points=mock_points,
                mute_outliers=mock_mute_outliers,
                dry_run=True)

            mock_points.find.return_value.sort.return_value.limit.return_value = iter([])

            mute_outliers(test_identifier, enabled, mock_config)

            mock_mute_outliers.update_one.assert_not_called()

    def test_no_mute_with_points(self):
        """ test no mute but points. """
        with patch(ns('get_mute')) as mock_get_mute:
            point = {'_id': 'id', 'some': 'value', 'results': []}
            mock_get_mute.return_value = None
            test_identifier = {
                'project': 'sys-perf',
                'variant': 'linux-standalone',
                'task': 'bestbuy-agg'
            }
            enabled = True
            mock_points = MagicMock(name='mock_points')
            mock_mute_outliers = MagicMock(name='mock_mute_outliers')
            mock_config = MagicMock(
                name='command_config',
                points=mock_points,
                mute_outliers=mock_mute_outliers,
                compact=True,
                dry_run=False)

            mock_points.find.return_value.sort.return_value.limit.return_value = iter([point])

            mute_outliers(test_identifier, enabled, mock_config)

            mock_mute_outliers.update_one.assert_called_with(
                test_identifier, {
                    '$currentDate': {
                        'last_updated_at': True
                    },
                    '$set': {
                        '_id': 'id',
                        'some': 'value',
                        'enabled': True,
                        'project': 'sys-perf',
                        'variant': 'linux-standalone',
                        'task': 'bestbuy-agg'
                    },
                },
                upsert=True)
