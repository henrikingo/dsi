"""
Unit tests for signal_processing/outliers/mark_outliers.py.
"""
# pylint: disable=missing-docstring
from __future__ import print_function

import unittest

from mock import MagicMock

from signal_processing.outliers.mark_outliers import get_identifier, mark_outlier, KEYS

NS = 'signal_processing.outliers'


def ns(relative_name):  # pylint: disable=invalid-name
    """Return a full name from a name relative to the tested module's name space."""
    return NS + '.' + relative_name


def create_identifier(suffix):
    return {key: key + suffix for key in KEYS}


class TestMarkOutlier(unittest.TestCase):
    """Tests for Mark Outlier."""

    def test_mark_outlier_with_no_found_outliers(self):
        config = MagicMock()

        mark_outlier({}, config)
        config.marked_outliers.update.assert_not_called()

    def test_mark_outlier_in_dry_run(self):
        config = MagicMock(dry_run=True)

        config.outliers.find_one.return_value = {'_id': 'id', 'outlier': 'outlier 1'}

        mark_outlier({}, config)
        config.marked_outliers.update.assert_not_called()

    def test_mark_outlier_with_found_outlier(self):
        config = MagicMock(dry_run=False)

        expected_id = create_identifier('0')
        identifier = expected_id.copy()
        identifier['_id'] = 'id'

        config.outliers.find_one.return_value = identifier

        mark_outlier({}, config)
        config.marked_outliers.update.assert_called_once()


class TestGetIdentifier(unittest.TestCase):
    """Tests for get_identifier."""

    def test_non_specified_keys_filtered_out(self):
        unknown_keys = ['key 0', 'unknown key 1', 'otherkey']
        point = create_identifier('0')
        for key in unknown_keys:
            point[key] = key

        identifier = get_identifier(point)

        for key in unknown_keys:
            self.assertNotIn(key, identifier)

        for key in KEYS:
            self.assertIn(key, identifier)
