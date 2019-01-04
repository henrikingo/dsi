"""
Unit tests for signal_processing/commands/change_points/list_build_failures.py.
"""
import unittest

import click.testing
from mock import MagicMock, patch

from signal_processing.change_points_cli import cli

NS = 'signal_processing.commands.change_points.list_build_failures'


def ns(relative_name):  # pylint: disable=invalid-name
    """Return a full name from a name relative to the tested module's name space."""
    return NS + '.' + relative_name


class TestListBuildFailures(unittest.TestCase):
    """
    Test list-build-failures command.
    """

    def setUp(self):
        self.runner = click.testing.CliRunner()

    # pylint: disable=unused-argument
    @patch(ns('list_build_failures.list_build_failures'), autospec=True)
    @patch('signal_processing.commands.helpers.CommandConfiguration', autospec=True)
    def test_list_build_failures_no_params(self, mock_config, mock_list_build_failures):
        """ Test list-build-failures requires parameters. """
        expected_config = MagicMock(name='config', debug=0, log_file='/tmp/log_file')
        mock_config.return_value = expected_config
        result = self.runner.invoke(cli, ['list-build-failures'])
        self.assertEqual(result.exit_code, 2)

    @patch(ns('helpers.process_excludes'), autospec=True)
    @patch(ns('list_build_failures.list_build_failures'), autospec=True)
    @patch(ns('helpers.process_params'), autospec=True)
    @patch('signal_processing.commands.helpers.CommandConfiguration', autospec=True)
    def test_list_build_failures(self, mock_config, mock_process_params, mock_list_build_failures,
                                 mock_process_excludes):
        """ Test list-build-failures. """
        expected_query = {'find': 'me'}
        mock_process_params.return_value = expected_query
        expected_excludes = 'exclude me'
        mock_process_excludes.return_value = expected_excludes
        expected_config = MagicMock(name='config', debug=0, log_file='/tmp/log_file')
        mock_config.return_value = expected_config

        result = self.runner.invoke(cli, ['list-build-failures', 'badf', 'sys-perf'])
        self.assertEqual(result.exit_code, 0)
        mock_process_params.assert_called_once_with('sys-perf', None, None, None, revision='badf')
        # Defaults `human_readable` to False.
        mock_list_build_failures.assert_called_once_with(expected_query, False, expected_config)

    @patch(ns('helpers.process_excludes'), autospec=True)
    @patch(ns('list_build_failures.list_build_failures'), autospec=True)
    @patch(ns('helpers.process_params'), autospec=True)
    @patch('signal_processing.commands.helpers.CommandConfiguration', autospec=True)
    def test_list_build_failures_params(self, mock_config, mock_process_params,
                                        mock_list_build_failures, mock_process_excludes):
        """ Test list-build-failures correctly uses parameters. """
        expected_query = {'find': 'me'}
        mock_process_params.return_value = expected_query
        expected_excludes = 'exclude me'
        mock_process_excludes.return_value = expected_excludes
        expected_config = MagicMock(name='config', debug=0, log_file='/tmp/log_file')
        mock_config.return_value = expected_config

        result = self.runner.invoke(cli, [
            'list-build-failures', 'badf', 'sys-perf', 'linux-standalone', 'industry_benchmarks',
            'ycsb_load', '--human-readable'
        ])
        self.assertEqual(result.exit_code, 0)
        # Never pass in `thread_level`.
        mock_process_params.assert_called_once_with(
            'sys-perf', 'linux-standalone', 'industry_benchmarks', 'ycsb_load', revision='badf')
        self.assertEqual(result.exit_code, 0)
        mock_list_build_failures.assert_called_once_with(expected_query, True, expected_config)
