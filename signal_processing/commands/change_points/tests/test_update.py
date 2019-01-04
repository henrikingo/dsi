"""
Unit tests for signal_processing/commands/change_points/update.py.
"""
import unittest

import click.testing
from mock import MagicMock, patch

from signal_processing.change_points_cli import cli
from signal_processing.commands import helpers

NS = 'signal_processing.commands.change_points.update'


def ns(relative_name):  # pylint: disable=invalid-name
    """Return a full name from a name relative to the tested module's name space."""
    return NS + '.' + relative_name


class TestUpdate(unittest.TestCase):
    """
    Test update command.
    """

    def setUp(self):
        self.runner = click.testing.CliRunner()

    def test_update_requires_some_params(self):
        """ Test update requires parameters. """
        result = self.runner.invoke(cli, ['update'])
        self.assertEqual(result.exit_code, 2)

    @patch(ns('helpers.process_excludes'), autospec=True)
    @patch(ns('update.update_change_points'), autospec=True)
    @patch(ns('helpers.process_params'), autospec=True)
    @patch('signal_processing.commands.helpers.CommandConfiguration', autospec=True)
    def test_update(self, mock_config, mock_process_params, mock_update, mock_process_excludes):
        """ Test update. """
        expected_query = {'find': 'me'}
        mock_process_params.return_value = expected_query
        expected_excludes = 'exclude me'
        mock_process_excludes.return_value = expected_excludes
        expected_config = MagicMock(name='config', debug=0, log_file='/tmp/log_file')
        mock_config.return_value = expected_config

        result = self.runner.invoke(cli, ['update', 'badf', 'sys-perf'])
        self.assertEqual(result.exit_code, 0)
        mock_process_params.assert_called_once_with(
            'sys-perf', None, None, None, revision='badf', thread_level=None)
        mock_process_excludes.assert_called_once_with(())
        # Defaults `processed_type` to hidden.
        mock_update.assert_called_once_with(helpers.PROCESSED_TYPE_HIDDEN, expected_query,
                                            expected_excludes, expected_config)

    @patch(ns('helpers.process_excludes'), autospec=True)
    @patch(ns('update.update_change_points'), autospec=True)
    @patch(ns('helpers.process_params'), autospec=True)
    @patch('signal_processing.commands.helpers.CommandConfiguration', autospec=True)
    def test_update_params(self, mock_config, mock_process_params, mock_update,
                           mock_process_excludes):
        """ Test update correctly uses parameters. """
        expected_query = {'find': 'me'}
        mock_process_params.return_value = expected_query
        expected_excludes = 'exclude me'
        mock_process_excludes.return_value = expected_excludes
        expected_config = MagicMock(name='config', debug=0, log_file='/tmp/log_file')
        mock_config.return_value = expected_config

        result = self.runner.invoke(cli, [
            'update', 'badf', 'sys-perf', 'linux-standalone', 'industry_benchmarks', 'ycsb_load',
            '1', '--exclude', 'fio', '--processed-type', 'acknowledged'
        ])
        self.assertEqual(result.exit_code, 0)
        mock_process_params.assert_called_once_with(
            'sys-perf',
            'linux-standalone',
            'industry_benchmarks',
            'ycsb_load',
            revision='badf',
            thread_level='1')
        mock_process_excludes.assert_called_once_with(('fio', ))
        mock_update.assert_called_once_with(helpers.PROCESSED_TYPE_ACKNOWLEDGED, expected_query,
                                            expected_excludes, expected_config)

    @patch(ns('helpers'), autospec=True)
    def test_update_type(self, mock_helpers):
        """ Test update correctly checks `processed-type` type. """
        expected_config = MagicMock(name='config', debug=0, log_file='/tmp/log_file')
        mock_helpers.CommandConfiguration.return_value = expected_config
        result = self.runner.invoke(cli, [
            'update', 'badf', 'sys-perf', 'linux-standalone', 'industry_benchmarks', 'ycsb_load',
            '1', '--exclude', 'fio', '--processed-type', 'incorrect type'
        ])
        self.assertEqual(result.exit_code, 2)
