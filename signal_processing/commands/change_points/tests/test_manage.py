"""
Unit tests for signal_processing/commands/change_points/manage.py.
"""
import unittest

import click.testing
from mock import MagicMock, patch

from signal_processing.change_points_cli import cli

NS = 'signal_processing.commands.change_points.manage'


def ns(relative_name):  # pylint: disable=invalid-name
    """Return a full name from a name relative to the tested module's name space."""
    return NS + '.' + relative_name


class TestManage(unittest.TestCase):
    """
    Test manage command.
    """

    def setUp(self):
        self.runner = click.testing.CliRunner()

    @patch(ns('manage.manage'), autospec=True)
    @patch('signal_processing.commands.helpers.CommandConfiguration', autospec=True)
    def test_manage(self, mock_config, mock_manage):
        """ Test manage. """
        expected_config = MagicMock(name='config', debug=0, log_file='/tmp/log_file')
        mock_config.return_value = expected_config

        result = self.runner.invoke(cli, ['manage'])
        self.assertEqual(result.exit_code, 0)
        mock_manage.assert_called_once_with(expected_config, (), False, False)

    @patch(ns('manage.manage'), autospec=True)
    @patch('signal_processing.commands.helpers.CommandConfiguration', autospec=True)
    def test_manage_with_collections(self, mock_config, mock_manage):
        """ Test manage. """
        expected_config = MagicMock(name='config', debug=0, log_file='/tmp/log_file')
        mock_config.return_value = expected_config

        result = self.runner.invoke(cli,
                                    ['manage', '--index', 'change_points', '--index', 'points'])
        self.assertEqual(result.exit_code, 0)
        mock_manage.assert_called_once_with(expected_config, ('change_points', 'points'), False,
                                            False)

    @patch(ns('manage.manage'), autospec=True)
    @patch('signal_processing.commands.helpers.CommandConfiguration', autospec=True)
    def test_manage_with_drop(self, mock_config, mock_manage):
        """ Test manage. """
        expected_config = MagicMock(name='config', debug=0, log_file='/tmp/log_file')
        mock_config.return_value = expected_config

        result = self.runner.invoke(cli, ['manage', '--drop'])
        self.assertEqual(result.exit_code, 0)
        mock_manage.assert_called_once_with(expected_config, (), True, False)

    @patch(ns('manage.manage'), autospec=True)
    @patch('signal_processing.commands.helpers.CommandConfiguration', autospec=True)
    def test_manage_with_force(self, mock_config, mock_manage):
        """ Test manage. """
        expected_config = MagicMock(name='config', debug=0, log_file='/tmp/log_file')
        mock_config.return_value = expected_config

        result = self.runner.invoke(cli, ['manage', '--force'])
        self.assertEqual(result.exit_code, 0)
        mock_manage.assert_called_once_with(expected_config, (), False, True)
