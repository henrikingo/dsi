"""
Unit tests for signal_processing/commands/outliers/mute_outliers.py.
"""
import unittest

import click.testing
from mock import MagicMock, patch

from signal_processing.outliers_cli import cli

NS = 'signal_processing.commands.outliers.mute_outliers'


def ns(relative_name):  # pylint: disable=invalid-name
    """Return a full name from a name relative to the tested module's name space."""
    return NS + '.' + relative_name


class TestMute(unittest.TestCase):
    """
    Test mute / unmute command.
    """

    def setUp(self):
        self.runner = click.testing.CliRunner()

    @patch(ns('mute.mute_outliers'))
    @patch('signal_processing.commands.helpers.CommandConfiguration', autospec=True)
    def test_mute_requires_params(self, mock_config, mock_mute):
        """ Test manage. """
        expected_config = MagicMock(name='config', debug=0, log_file='/tmp/log_file')
        mock_config.return_value = expected_config

        result = self.runner.invoke(cli, ['mute'])
        self.assertEqual(result.exit_code, 2)
        mock_mute.assert_not_called()

    @patch(ns('mute.mute_outliers'))
    @patch('signal_processing.commands.helpers.CommandConfiguration', autospec=True)
    def test_unmute_requires_params(self, mock_config, mock_mute):
        """ Test manage. """
        expected_config = MagicMock(name='config', debug=0, log_file='/tmp/log_file')
        mock_config.return_value = expected_config

        result = self.runner.invoke(cli, ['unmute'])
        self.assertEqual(result.exit_code, 2)
        mock_mute.assert_not_called()

    def _test(self, mock_config, mock_mute, mute=True, revision=None):
        """ test mute helper. """
        expected_config = MagicMock(name='config', debug=0, log_file='/tmp/log_file')
        mock_config.return_value = expected_config

        test_identifier = {
            'project': 'sys-perf',
            'variant': 'linux-1-node-replSet',
            'task': 'bestbuy_query',
            'test': 'canary_client-cpuloop-10x',
            'thread_level': '1',
        }
        if revision:
            test_identifier['suspect_revision'] = 'badf00d'

        parameters = [
            'mute' if mute else 'unmute', test_identifier['project'], test_identifier['variant'],
            test_identifier['task'], test_identifier['test'], test_identifier['thread_level']
        ]
        if revision:
            parameters.append('--revision')
            parameters.append(revision)
        result = self.runner.invoke(cli, parameters)
        self.assertEqual(result.exit_code, 0)
        if revision:
            test_identifier['revision'] = revision
            del test_identifier['suspect_revision']
        mock_mute.assert_called_once_with(test_identifier, mute, expected_config)

    @patch(ns('mute.mute_outliers'), autospec=True)
    @patch('signal_processing.commands.helpers.CommandConfiguration', autospec=True)
    def test_mute_with_revision(self, mock_config, mock_mute):
        """ Test mute with revision. """
        self._test(mock_config, mock_mute, revision='badf00d')

    @patch(ns('mute.mute_outliers'), autospec=True)
    @patch('signal_processing.commands.helpers.CommandConfiguration', autospec=True)
    def test_mute_no_revision(self, mock_config, mock_mute):
        """ Test mute no revision. """
        self._test(mock_config, mock_mute)

    @patch(ns('mute.mute_outliers'), autospec=True)
    @patch('signal_processing.commands.helpers.CommandConfiguration', autospec=True)
    def test_unmute_with_revision(self, mock_config, mock_mute):
        """ Test mute with revision. """
        self._test(mock_config, mock_mute, mute=False, revision='badf00d')

    @patch(ns('mute.mute_outliers'), autospec=True)
    @patch('signal_processing.commands.helpers.CommandConfiguration', autospec=True)
    def test_unmute(self, mock_config, mock_unmute):
        """ Test manage. """
        self._test(mock_config, mock_unmute, mute=False)
