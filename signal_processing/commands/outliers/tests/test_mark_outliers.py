"""
Unit tests for signal_processing/commands/outliers/mark_outliers.py.
"""
import unittest

import click.testing
from mock import MagicMock, patch

from signal_processing.outliers_cli import cli

NS = 'signal_processing.commands.outliers.mark_outliers'


def ns(relative_name):  # pylint: disable=invalid-name
    """Return a full name from a name relative to the tested module's name space."""
    return NS + '.' + relative_name


class TestMarkOutliers(unittest.TestCase):
    """
    Test mark outliers.
    """

    def setUp(self):
        self.runner = click.testing.CliRunner()

    @patch('signal_processing.commands.helpers.CommandConfiguration', autospec=True)
    def test_mark_outliers_requires_params(self, mock_config):
        """ Test list mutes requires params. """
        expected_config = MagicMock(name='config', debug=0, log_file='/tmp/log_file')
        mock_config.return_value = expected_config

        result = self.runner.invoke(cli, ['mark'])
        self.assertEqual(result.exit_code, 2)

    @patch(ns('mark_outliers.mark_outlier'))
    @patch('signal_processing.commands.helpers.CommandConfiguration', autospec=True)
    def test_mark_outliers(self, mock_config, mock_mark_outliers):
        """ Test list mutes requires params. """
        expected_config = MagicMock(name='config', debug=0, log_file='/tmp/log_file')
        mock_config.return_value = expected_config

        result = self.runner.invoke(cli, [
            'mark', 'revision', 'project', 'variant', 'task', 'test', 'thread_level', '--confirmed'
        ])
        self.assertEqual(result.exit_code, 0)
        mock_mark_outliers.assert_called_once()
