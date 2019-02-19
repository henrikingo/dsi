"""
Unit tests for signal_processing/commands/outliers/unmark_outliers.py.
"""
import unittest

import click.testing
from mock import MagicMock, patch

from signal_processing.outliers_cli import cli

NS = 'signal_processing.commands.outliers.unmark_outliers'


def ns(relative_name):  # pylint: disable=invalid-name
    """Return a full name from a name relative to the tested module's name space."""
    return NS + '.' + relative_name


class TestUnmarkOutliers(unittest.TestCase):
    """
    Test unmark outliers.
    """

    def setUp(self):
        self.runner = click.testing.CliRunner()

    @patch('signal_processing.commands.helpers.CommandConfiguration', autospec=True)
    def test_unmark_outliers_requires_params(self, mock_config):
        """ Test list mutes requires params. """
        expected_config = MagicMock(name='config', debug=0, log_file='/tmp/log_file')
        mock_config.return_value = expected_config

        result = self.runner.invoke(cli, ['unmark'])
        self.assertEqual(result.exit_code, 2)

    @patch(ns('unmark_outliers.unmark_outlier'))
    @patch('signal_processing.commands.helpers.CommandConfiguration', autospec=True)
    def test_unmark_outliers(self, mock_config, mock_unmark_outliers):
        """ Test list mutes requires params. """
        expected_config = MagicMock(name='config', debug=0, log_file='/tmp/log_file')
        mock_config.return_value = expected_config

        result = self.runner.invoke(
            cli, ['unmark', 'revision', 'project', 'variant', 'task', 'test', 'thread_level'])
        self.assertEqual(result.exit_code, 0)
        mock_unmark_outliers.assert_called_once()
