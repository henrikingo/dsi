"""
Unit tests for signal_processing/commands/outliers/config_command.py.
"""
# pylint: disable=missing-docstring
from __future__ import print_function
import unittest

from mock import MagicMock, patch

from click.testing import CliRunner

from signal_processing.outliers_cli import cli


class ClickTest(unittest.TestCase):
    """
    Test Cli group command.
    """

    def setUp(self):
        self.runner = CliRunner()


class TestOutliersParams(ClickTest):
    """
    Test config command.
    """

    def test_requires_params(self):
        """ Test outliers with no parameters. """

        result = self.runner.invoke(cli, ['test'])
        self.assertEqual(result.exit_code, 2)

    def test_help_h_option(self):
        """ Test help with the `-h` option. """
        result = self.runner.invoke(cli, ['-h'])
        self.assertEqual(result.exit_code, 0)
        self.assertTrue(result.output.startswith("Usage"))

    @patch('signal_processing.change_points.jobs.process_jobs', autospec=True)
    @patch('signal_processing.change_points.helpers.CommandConfiguration', autospec=True)
    def test_basic(self, mock_command_config_cls, mock_process_jobs):
        """ Test compute. """
        mock_points = MagicMock(name='config')
        mock_points.aggregate.return_value = ()
        expected_config = MagicMock(
            name='config', points=mock_points, debug=0, log_file='/tmp/log_file')
        mock_command_config_cls.return_value = expected_config
        mock_process_jobs.return_value.__enter__.return_value = ()

        result = self.runner.invoke(cli, ['config', 'sys-perf'])
        self.assertEqual(result.exit_code, 0)

    @patch('signal_processing.change_points.helpers.process_params', autospec=True)
    @patch('signal_processing.change_points.helpers.CommandConfiguration', autospec=True)
    def test_no_jobs(self, mock_config, mock_process_params):
        """ Test mark correctly uses parameters. """
        expected_query = {'find': 'me'}
        mock_process_params.return_value = expected_query
        expected_config = MagicMock(name='config', debug=0, log_file='/tmp/log_file')
        mock_config.return_value = expected_config

        result = self.runner.invoke(
            cli,
            ['config', 'sys-perf', 'linux-standalone', 'industry_benchmarks', 'ycsb_load', '1'])
        self.assertEqual(result.exit_code, 0)
        mock_process_params.assert_called_once_with(
            'sys-perf', 'linux-standalone', 'industry_benchmarks', 'ycsb_load', thread_level='1')
