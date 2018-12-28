"""
Unit tests for signal_processing/commands/change_points/list_build_failures.py.
"""

import unittest

from mock import MagicMock, patch

from signal_processing.commands.change_points.list_build_failures import list_build_failures


class TestListBuildFailures(unittest.TestCase):
    """
    Test suite for list_build_failures method.
    """

    @patch(
        'signal_processing.commands.change_points.list_build_failures.stringify_json',
        autospec=True)
    def test_list_build_failures(self, mock_stringify_json):
        """ Test that list_build_failures works with default configuration."""

        mock_find = MagicMock(name='find', return_value=[{}])
        mock_linked_build_failures = MagicMock(name='linked_build_failures', find=mock_find)
        mock_database = MagicMock(name='database', linked_build_failures=mock_linked_build_failures)
        query = {'find': 'me'}
        human_readable = False
        mock_config = MagicMock(name='config', database=mock_database, compact=True)
        list_build_failures(query, human_readable, mock_config)
        mock_find.assert_called_once_with(query)
        mock_stringify_json.assert_called_once_with(mock_find.return_value[0], mock_config.compact)

    @patch(
        'signal_processing.commands.change_points.list_build_failures.stringify_json',
        autospec=True)
    def test_maps_fieldnames(self, mock_stringify_json):
        """ Test that list_build_failures remaps field names."""

        mock_find = MagicMock(name='find', return_value=[{}])
        mock_linked_build_failures = MagicMock(name='linked_build_failures', find=mock_find)
        mock_database = MagicMock(name='database', linked_build_failures=mock_linked_build_failures)
        query = {
            'find': 'me',
            'variant': 'variant name',
            'task': 'taskname',
            'suspect_revision': 'revision'
        }
        expected = {
            'find': 'me',
            'buildvariants': 'variant name',
            'tasks': 'taskname',
            'revision': 'revision'
        }

        human_readable = False
        mock_config = MagicMock(name='config', database=mock_database, compact=True)
        list_build_failures(query, human_readable, mock_config)
        mock_find.assert_called_once_with(expected)
        mock_stringify_json.assert_called_once_with(mock_find.return_value[0], mock_config.compact)

    @patch(
        'signal_processing.commands.change_points.list_build_failures.stringify_json',
        autospec=True)
    def test_list_build_failures_expanded(self, mock_stringify_json):
        """ Test that list_build_failures works with the `expanded` option."""

        mock_find = MagicMock(name='find', return_value=[{}])
        mock_linked_build_failures = MagicMock(name='linked_build_failures', find=mock_find)
        mock_database = MagicMock(name='database', linked_build_failures=mock_linked_build_failures)
        query = {'find': 'me'}
        human_readable = False
        mock_config = MagicMock(name='config', database=mock_database, compact=False)
        list_build_failures(query, human_readable, mock_config)
        mock_stringify_json.assert_called_once_with(mock_find.return_value[0], mock_config.compact)

    @patch(
        'signal_processing.commands.change_points.list_build_failures.stringify_json',
        autospec=True)
    @patch(
        'signal_processing.commands.change_points.list_build_failures._print_human_readable',
        autospec=True)
    def test_list_build_failures_human_readable(self, mock__print_human_readable,
                                                mock_stringify_json):
        """ Test that list_build_failures works with the `human_readable` option."""

        mock_find = MagicMock(name='find', return_value=[{}])
        mock_linked_build_failures = MagicMock(name='linked_build_failures', find=mock_find)
        mock_database = MagicMock(name='database', linked_build_failures=mock_linked_build_failures)
        query = {'find': 'me'}
        human_readable = True
        mock_config = MagicMock(name='config', database=mock_database, compact=False)
        list_build_failures(query, human_readable, mock_config)
        mock__print_human_readable.assert_called_once_with(mock_find.return_value[0])

    # TODO: Add autospec=True to patch below once we upgrade to Python3 (PERF-1254). Cannot call
    # `assert_not_called` with autospeccing due to https://bugs.python.org/issue28380. This bug has
    # a fix for Python3 only.
    @patch('signal_processing.commands.change_points.list_build_failures.stringify_json')
    @patch(
        'signal_processing.commands.change_points.list_build_failures._print_human_readable',
        autospec=True)
    def test_list_build_failures_human_readable_and_expanded(self, mock__print_human_readable,
                                                             mock_stringify_json):
        """ Test that even if `expanded` option set, `human_readable` takes precedence."""

        mock_find = MagicMock(name='find', return_value=[{}])
        mock_linked_build_failures = MagicMock(name='linked_build_failures', find=mock_find)
        mock_database = MagicMock(name='database', linked_build_failures=mock_linked_build_failures)
        query = {'find': 'me'}
        human_readable = True
        mock_config = MagicMock(name='config', database=mock_database, compact=True)
        list_build_failures(query, human_readable, mock_config)
        mock__print_human_readable.assert_called_once_with(mock_find.return_value[0])
        mock_stringify_json.assert_not_called()
