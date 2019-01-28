"""
Unit tests for signal_processing/change_points/list_build_failures.py.
"""

import unittest

from mock import MagicMock, patch

from signal_processing.change_points import list_build_failures

NS = 'signal_processing.change_points.list_build_failures'


def ns(relative_name):  # pylint: disable=invalid-name
    """Return a full name from a name relative to the tested module's name space."""
    return NS + '.' + relative_name


def generate_mock_bf(index):
    return {
        '_id': 'BF-' + index,
        'summary': 'summary ' + index,
        'revision': 'revision ' + index,
        'first_failing_revision': 'first failing revision ' + index,
    }


def generate_mock_bfs(count):
    """
    Generate the specified number of mock BFs.

    :param count: Number of bfs to generate.
    :return: a list of mock BFs.
    """
    return [generate_mock_bf(str(index)) for index in range(count)]


class TestListBuildFailures(unittest.TestCase):
    """
    Test suite for list_build_failures method.
    """

    @patch(ns('stringify_json'), autospec=True)
    def test_list_build_failures(self, mock_stringify_json):
        """ Test that list_build_failures works with default configuration."""

        mock_find = MagicMock(name='find', return_value=[{}])
        mock_linked_build_failures = MagicMock(name='linked_build_failures', find=mock_find)
        mock_database = MagicMock(name='database', linked_build_failures=mock_linked_build_failures)
        query = {'find': 'me'}
        human_readable = False
        mock_config = MagicMock(name='config', database=mock_database, compact=True)
        list_build_failures.list_build_failures(query, human_readable, mock_config)
        mock_find.assert_called_once_with(query)
        mock_stringify_json.assert_called_once_with(mock_find.return_value[0], mock_config.compact)

    @patch(ns('stringify_json'), autospec=True)
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
        list_build_failures.list_build_failures(query, human_readable, mock_config)
        mock_find.assert_called_once_with(expected)
        mock_stringify_json.assert_called_once_with(mock_find.return_value[0], mock_config.compact)

    @patch(ns('stringify_json'), autospec=True)
    def test_list_build_failures_expanded(self, mock_stringify_json):
        """ Test that list_build_failures works with the `expanded` option."""

        mock_find = MagicMock(name='find', return_value=[{}])
        mock_linked_build_failures = MagicMock(name='linked_build_failures', find=mock_find)
        mock_database = MagicMock(name='database', linked_build_failures=mock_linked_build_failures)
        query = {'find': 'me'}
        human_readable = False
        mock_config = MagicMock(name='config', database=mock_database, compact=False)
        list_build_failures.list_build_failures(query, human_readable, mock_config)
        mock_stringify_json.assert_called_once_with(mock_find.return_value[0], mock_config.compact)

    def test_list_build_failures_human_readable(self):
        """ Test that list_build_failures works with the `human_readable` option."""
        human_readable = list_build_failures.render_human_readable_bfs([])
        self.assertEqual(1, len(human_readable.strip().split('\n')))

    def test_list_build_failures_human_readable_and_expanded(self):
        """ Test that even if `expanded` option set, `human_readable` takes precedence."""
        n_bfs = 5
        mock_bfs = generate_mock_bfs(n_bfs)
        human_readable = list_build_failures.render_human_readable_bfs(mock_bfs)
        self.assertEqual(n_bfs * 12, len(human_readable.strip().split('\n')))

        for mock_bf in mock_bfs:
            self.assertIn(list_build_failures.JIRA_LINK_PREFIX + mock_bf['_id'], human_readable)
