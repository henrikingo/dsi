"""
Unit tests for signal_processing/outliers/manage.py.
"""
import unittest

from mock import MagicMock, call, patch

from signal_processing.outliers import manage

NS = 'signal_processing.outliers.manage'


def ns(relative_name):  # pylint: disable=invalid-name
    """Return a full name from a name relative to the tested module's name space."""
    return NS + '.' + relative_name


class TestManage(unittest.TestCase):
    """Test for the manage function."""

    @patch(ns('create_outliers_indexes'))
    def test_manage(self, create_indexes_mock):
        mock_command_config = MagicMock()
        manage.manage(mock_command_config)
        create_indexes_mock.assert_called_with(mock_command_config)


class TestCreateOutliersIndexes(unittest.TestCase):
    """Tests for create_outliers_indexes."""

    def test_create_outliers_indexes(self):
        mock_collection = MagicMock()
        mock_command_config = MagicMock(outliers=mock_collection)
        manage.create_outliers_indexes(mock_command_config)

        calls = [
            call([('project', 1), ('variant', 1), ('task', 1), ('test', 1), ('order', 1)]),
        ]
        mock_collection.create_index.assert_has_calls(calls)
