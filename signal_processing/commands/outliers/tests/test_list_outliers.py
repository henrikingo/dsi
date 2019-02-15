"""
Unit tests for signal_processing/commands/outliers/list_mutes.py.
"""
import unittest

import click.testing
from mock import MagicMock, patch

from signal_processing.detect_outliers import DETECTED_TYPE
from signal_processing.outliers_cli import cli

NS = 'signal_processing.commands.outliers.list_outliers'


def ns(relative_name):  # pylint: disable=invalid-name
    """Return a full name from a name relative to the tested module's name space."""
    return NS + '.' + relative_name


class TestListOutliers(unittest.TestCase):
    """
    Test list outliers command.
    """

    def setUp(self):
        self.runner = click.testing.CliRunner()

    @patch('signal_processing.commands.helpers.CommandConfiguration', autospec=True)
    def test_list_outliers_requires_params(self, mock_config):
        """ Test list mutes requires params. """
        expected_config = MagicMock(name='config', debug=0, log_file='/tmp/log_file')
        mock_config.return_value = expected_config

        result = self.runner.invoke(cli, ['list'])
        self.assertEqual(result.exit_code, 2)

    @patch(ns('list_outliers.list_outliers'), autospec=True)
    @patch('signal_processing.commands.helpers.CommandConfiguration', autospec=True)
    def test_list_outliers(self, mock_config, mock_list_outliers):
        """ Test list mutes. """
        expected_config = MagicMock(name='config', debug=0, log_file='/tmp/log_file')
        mock_config.return_value = expected_config

        project = 'sys-perf'
        result = self.runner.invoke(cli, ['list', project])
        self.assertEqual(result.exit_code, 0)
        query = {'project': project}
        human_readable = True
        limit = None
        no_older_than = 14
        marked = False
        types = (DETECTED_TYPE, )
        mock_list_outliers.assert_called_once_with(query, marked, types, human_readable, limit,
                                                   no_older_than, expected_config)

    @patch(ns('list_outliers.list_outliers'), autospec=True)
    @patch('signal_processing.commands.helpers.CommandConfiguration', autospec=True)
    def test_list_outliers_with_revision(self, mock_config, mock_list_outliers):
        """ Test list mutes. """
        expected_config = MagicMock(name='config', debug=0, log_file='/tmp/log_file')
        mock_config.return_value = expected_config

        project = 'sys-perf'
        revision = 'revision'
        result = self.runner.invoke(cli, ['list', project, '--revision', revision])
        self.assertEqual(result.exit_code, 0)
        query = {'project': project, 'suspect_revision': revision}
        human_readable = True
        limit = None
        no_older_than = 14
        marked = False
        types = (DETECTED_TYPE, )
        mock_list_outliers.assert_called_once_with(query, marked, types, human_readable, limit,
                                                   no_older_than, expected_config)
