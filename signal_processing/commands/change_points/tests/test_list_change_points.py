"""
Unit tests for signal_processing/commands/change_points/list_change_points.py.
"""
import unittest

import click.testing
import mock
from mock import patch

from signal_processing.change_points_cli import cli

NS = 'signal_processing.commands.change_points.list_change_points'


def ns(relative_name):  # pylint: disable=invalid-name
    """Return a full name from a name relative to the tested module's name space."""
    return NS + '.' + relative_name


class TestList(unittest.TestCase):
    """
    Test list command.
    """

    def setUp(self):
        self.runner = click.testing.CliRunner()

    # pylint: disable=unused-argument
    @patch(ns('list_change_points.list_change_points'), autospec=True)
    def test_list_check_return(self, mock_list):
        """ Test list with no parameters. """
        result = self.runner.invoke(cli, ['list'])
        self.assertEqual(result.exit_code, 0)

    @patch(ns('list_change_points.list_change_points'))
    def test_list_check_defaults(self, mock_list):
        """ Test list check default parameters. """
        self.runner.invoke(cli, ['list'])
        mock_list.assert_called_once()
        _, kwargs = mock_list.call_args
        self.assertEquals(
            kwargs, {
                'change_point_type': 'unprocessed',
                'query': {},
                'limit': 10,
                'no_older_than': 14,
                'human_readable': True,
                'hide_canaries': True,
                'hide_wtdevelop': True,
                'exclude_patterns': [],
                'command_config': mock.ANY,
                'processed_types': ('acknowledged', )
            })

    @patch(ns('helpers.process_excludes'), autospec=True)
    @patch(ns('list_change_points.list_change_points'))
    def test_list_excludes(self, mock_list, mock_process_excludes):
        """ Test list --exclude. """
        mock_process_excludes.return_value = 'excludes'
        self.runner.invoke(cli, ['list', '--exclude', 'pattern'])
        mock_process_excludes.assert_called_once_with(('pattern', ))
        mock_list.assert_called_once()
        _, kwargs = mock_list.call_args
        self.assertEquals(kwargs['exclude_patterns'], 'excludes')

    @patch(ns('helpers.process_excludes'), autospec=True)
    @patch(ns('list_change_points.list_change_points'))
    def test_list_multiple_excludes(self, mock_list, mock_process_excludes):
        """ Test list --exclude. """
        mock_process_excludes.return_value = 'excludes'
        self.runner.invoke(cli, ['list', '--exclude', 'pattern1', '--exclude', 'pattern2'])
        mock_process_excludes.assert_called_once_with((
            'pattern1',
            'pattern2',
        ))
        mock_list.assert_called_once()
        _, kwargs = mock_list.call_args
        self.assertEquals(kwargs['exclude_patterns'], 'excludes')

    @patch(ns('list_change_points.list_change_points'))
    def test_list_unprocessed(self, mock_list):
        """ Test list unprocessed. """
        result = self.runner.invoke(cli, ['list', '--point-type', 'unprocessed'])
        mock_list.assert_called_once()
        _, kwargs = mock_list.call_args
        self.assertEquals(kwargs['change_point_type'], 'unprocessed')
        self.assertEqual(result.exit_code, 0)

    @patch(ns('list_change_points.list_change_points'))
    def test_list_processed(self, mock_list):
        """ Test list processed. """
        result = self.runner.invoke(cli, ['list', '--point-type', 'processed'])
        mock_list.assert_called_once()
        _, kwargs = mock_list.call_args
        self.assertEquals(kwargs['change_point_type'], 'processed')
        self.assertEqual(result.exit_code, 0)

    @patch(ns('list_change_points.list_change_points'))
    def test_list_raw(self, mock_list):
        """ Test list raw. """
        result = self.runner.invoke(cli, ['list', '--point-type', 'raw'])
        mock.Mock.assert_called_once(mock_list)
        mock_list.assert_called_once()
        _, kwargs = mock_list.call_args
        self.assertEquals(kwargs['change_point_type'], 'raw')
        self.assertEqual(result.exit_code, 0)

    def test_list_invalid(self):
        """ Test list invalid. """
        result = self.runner.invoke(cli, ['list', '--point-type', 'war'])
        self.assertEqual(result.exit_code, 2)

    @patch(ns('list_change_points.list_change_points'))
    def test_list_limit(self, mock_list):
        """ Test list check --limit 10. """
        self.runner.invoke(cli, ['list', '--limit', '10'])
        mock_list.assert_called_once()
        _, kwargs = mock_list.call_args
        self.assertEquals(kwargs['limit'], 10)

    @patch(ns('list_change_points.list_change_points'))
    def test_list_limit_none(self, mock_list):
        """ Test list check --limit None. """
        self.runner.invoke(cli, ['list', '--limit', 'None'])
        mock_list.assert_called_once()
        _, kwargs = mock_list.call_args
        self.assertIsNone(kwargs['limit'])

    @patch(ns('list_change_points.list_change_points'))
    def test_list_no_older(self, mock_list):
        """ Test list check --non-older-than 1. """
        self.runner.invoke(cli, ['list', '--no-older-than', '1'])
        mock_list.assert_called_once()
        _, kwargs = mock_list.call_args
        self.assertEquals(kwargs['no_older_than'], 1)

    @patch(ns('list_change_points.list_change_points'))
    def test_list_no_older_none(self, mock_list):
        """ Test list check --non-older-than None. """
        self.runner.invoke(cli, ['list', '--no-older-than', 'None'])
        mock_list.assert_called_once()
        _, kwargs = mock_list.call_args
        self.assertEquals(kwargs['no_older_than'], None)

    @patch(ns('list_change_points.list_change_points'))
    def test_list_human_readable(self, mock_list):
        """ Test list check --no-human-readable. """
        self.runner.invoke(cli, ['list', '--human-readable'])
        mock_list.assert_called_once()
        _, kwargs = mock_list.call_args
        self.assertEquals(kwargs['human_readable'], True)

    @patch(ns('list_change_points.list_change_points'))
    def test_list_no_human_readable(self, mock_list):
        """ Test list check --no-human-readable. """
        self.runner.invoke(cli, ['list', '--no-human-readable'])
        mock_list.assert_called_once()
        _, kwargs = mock_list.call_args
        self.assertEquals(kwargs['human_readable'], False)

    @patch(ns('list_change_points.list_change_points'))
    def test_list_show_canaries(self, mock_list):
        """ Test list check --show-canaries. """
        self.runner.invoke(cli, ['list', '--show-canaries'])
        mock_list.assert_called_once()
        _, kwargs = mock_list.call_args
        self.assertEquals(kwargs['hide_canaries'], False)

    @patch(ns('list_change_points.list_change_points'))
    def test_list_hide_canaries(self, mock_list):
        """ Test list check --hide-canaries. """
        self.runner.invoke(cli, ['list', '--hide-canaries'])
        mock_list.assert_called_once()
        _, kwargs = mock_list.call_args
        self.assertEquals(kwargs['hide_canaries'], True)

    @patch(ns('list_change_points.list_change_points'))
    def test_list_show_wtdevelop(self, mock_list):
        """ Test list check --show-wtdevelop. """
        self.runner.invoke(cli, ['list', '--show-wtdevelop'])
        mock_list.assert_called_once()
        _, kwargs = mock_list.call_args
        self.assertEquals(kwargs['hide_wtdevelop'], False)

    @patch(ns('list_change_points.list_change_points'))
    def test_list_hide_wtdevelop(self, mock_list):
        """ Test list check --hide-wtdevelop. """
        self.runner.invoke(cli, ['list', '--hide-wtdevelop'])
        mock_list.assert_called_once()
        _, kwargs = mock_list.call_args
        self.assertEquals(kwargs['hide_wtdevelop'], True)
