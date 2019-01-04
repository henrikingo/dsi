"""
Unit tests for signal_processing/commands/change_points/mark.py.
"""
import unittest

import click.testing
from mock import MagicMock, patch

from signal_processing.change_points_cli import cli
from signal_processing.commands import helpers

NS = 'signal_processing.commands.change_points.mark'


def ns(relative_name):  # pylint: disable=invalid-name
    """Return a full name from a name relative to the tested module's name space."""
    return NS + '.' + relative_name


class TestMark(unittest.TestCase):
    """
    Test mark command.
    """

    def setUp(self):
        self.runner = click.testing.CliRunner()

    def test_mark_requires_some_params(self):
        """ Test mark requires parameters. """
        result = self.runner.invoke(cli, ['mark'])
        self.assertEqual(result.exit_code, 2)

    @patch(ns('helpers.process_excludes'), autospec=True)
    @patch(ns('mark.mark_change_points'), autospec=True)
    @patch(ns('helpers.process_params'), autospec=True)
    @patch('signal_processing.commands.helpers.CommandConfiguration', autospec=True)
    def test_mark(self, mock_config, mock_process_params, mock_mark, mock_process_excludes):
        """ Test mark. """
        expected_query = {'find': 'me'}
        mock_process_params.return_value = expected_query
        expected_excludes = 'exclude me'
        mock_process_excludes.return_value = expected_excludes

        expected_config = MagicMock(name='config', debug=0, log_file='/tmp/log_file')
        mock_config.return_value = expected_config

        result = self.runner.invoke(cli, ['mark', 'badf', 'sys-perf'])
        self.assertEqual(result.exit_code, 0)
        mock_process_params.assert_called_once_with(
            'sys-perf', None, None, None, revision='badf', thread_level=None)
        mock_process_excludes.assert_called_once_with(())
        mock_mark.assert_called_once_with(helpers.PROCESSED_TYPE_ACKNOWLEDGED, expected_query,
                                          expected_excludes, expected_config)

    @patch(ns('helpers.process_excludes'), autospec=True)
    @patch(ns('mark.mark_change_points'), autospec=True)
    @patch(ns('helpers.process_params'), autospec=True)
    @patch('signal_processing.commands.helpers.CommandConfiguration', autospec=True)
    def test_mark_params(self, mock_config, mock_process_params, mock_mark, mock_process_excludes):
        """ Test mark correctly uses parameters. """
        expected_query = {'find': 'me'}
        mock_process_params.return_value = expected_query
        expected_excludes = 'exclude me'
        mock_process_excludes.return_value = expected_excludes
        expected_config = MagicMock(name='config', debug=0, log_file='/tmp/log_file')
        mock_config.return_value = expected_config

        result = self.runner.invoke(cli, [
            'mark', 'badf', 'sys-perf', 'linux-standalone', 'industry_benchmarks', 'ycsb_load', '1',
            '--exclude', 'fio'
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
        mock_mark.assert_called_once_with(helpers.PROCESSED_TYPE_ACKNOWLEDGED, expected_query,
                                          expected_excludes, expected_config)


class TestHide(unittest.TestCase):
    """
    Test hide command.
    """

    def setUp(self):
        self.runner = click.testing.CliRunner()

    def test_hide_requires_some_params(self):
        """ Test hide requires parameters. """
        result = self.runner.invoke(cli, ['hide'])
        self.assertEqual(result.exit_code, 2)

    @patch(ns('helpers.process_excludes'), autospec=True)
    @patch(ns('mark.mark_change_points'), autospec=True)
    @patch(ns('helpers.process_params'), autospec=True)
    @patch('signal_processing.commands.helpers.CommandConfiguration', autospec=True)
    def test_hide(self, mock_config, mock_process_params, mock_mark, mock_process_excludes):
        """ Test hide. """
        expected_query = {'find': 'me'}
        mock_process_params.return_value = expected_query
        expected_excludes = 'exclude me'
        mock_process_excludes.return_value = expected_excludes
        expected_config = MagicMock(name='config', debug=0, log_file='/tmp/log_file')
        mock_config.return_value = expected_config

        result = self.runner.invoke(cli, ['hide', 'badf', 'sys-perf'])
        self.assertEqual(result.exit_code, 0)
        mock_process_params.assert_called_once_with(
            'sys-perf', None, None, None, revision='badf', thread_level=None)
        mock_process_excludes.assert_called_once_with(())
        mock_mark.assert_called_once_with(helpers.PROCESSED_TYPE_HIDDEN, expected_query,
                                          expected_excludes, expected_config)

    @patch(ns('helpers.process_excludes'), autospec=True)
    @patch(ns('mark.mark_change_points'), autospec=True)
    @patch(ns('helpers.process_params'), autospec=True)
    @patch('signal_processing.commands.helpers.CommandConfiguration', autospec=True)
    def test_hide_params(self, mock_config, mock_process_params, mock_mark, mock_process_excludes):
        """ Test hide correctly uses parameters. """
        expected_query = {'find': 'me'}
        mock_process_params.return_value = expected_query
        expected_excludes = 'exclude me'
        mock_process_excludes.return_value = expected_excludes
        expected_config = MagicMock(name='config', debug=0, log_file='/tmp/log_file')
        mock_config.return_value = expected_config

        result = self.runner.invoke(cli, [
            'hide', 'badf', 'sys-perf', 'linux-standalone', 'industry_benchmarks', 'ycsb_load', '1',
            '--exclude', 'fio'
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
        mock_mark.assert_called_once_with(helpers.PROCESSED_TYPE_HIDDEN, expected_query,
                                          expected_excludes, expected_config)
