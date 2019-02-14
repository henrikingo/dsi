"""
Unit tests for signal_processing/commands/outliers/list_mutes.py.
"""
import unittest

import click.testing
from mock import MagicMock, patch

from signal_processing.outliers_cli import cli

NS = 'signal_processing.commands.outliers.list_mutes'


def ns(relative_name):  # pylint: disable=invalid-name
    """Return a full name from a name relative to the tested module's name space."""
    return NS + '.' + relative_name


class TestListMutes(unittest.TestCase):
    """
    Test list mutes command.
    """

    def setUp(self):
        self.runner = click.testing.CliRunner()

    @patch('signal_processing.commands.helpers.CommandConfiguration', autospec=True)
    def test_list_mutes_requires_params(self, mock_config):
        """ Test list mutes requires params. """
        expected_config = MagicMock(name='config', debug=0, log_file='/tmp/log_file')
        mock_config.return_value = expected_config

        result = self.runner.invoke(cli, ['list-mutes'])
        self.assertEqual(result.exit_code, 2)

    @patch(ns('list_mutes.list_mutes'), autospec=True)
    @patch('signal_processing.commands.helpers.CommandConfiguration', autospec=True)
    def test_list_mutes(self, mock_config, mock_list_mutes):
        """ Test list mutes. """
        expected_config = MagicMock(name='config', debug=0, log_file='/tmp/log_file')
        mock_config.return_value = expected_config

        project = 'sys-perf'
        result = self.runner.invoke(cli, ['list-mutes', project])
        self.assertEqual(result.exit_code, 0)
        query = {'project': project}
        human_readable = True
        limit = None
        no_older_than = None
        mock_list_mutes.assert_called_once_with(query, human_readable, limit, no_older_than,
                                                expected_config)

    @patch(ns('list_mutes.list_mutes'), autospec=True)
    @patch('signal_processing.commands.helpers.CommandConfiguration', autospec=True)
    def test_list_mutes_with_revision(self, mock_config, mock_list_mutes):
        """ Test list mutes. """
        expected_config = MagicMock(name='config', debug=0, log_file='/tmp/log_file')
        mock_config.return_value = expected_config

        project = 'sys-perf'
        revision = 'revision'
        result = self.runner.invoke(cli, ['list-mutes', project, '--revision', revision])
        self.assertEqual(result.exit_code, 0)
        query = {'project': project, 'suspect_revision': revision}
        human_readable = True
        limit = None
        no_older_than = None
        mock_list_mutes.assert_called_once_with(query, human_readable, limit, no_older_than,
                                                expected_config)
