"""
Unit tests for signal_processing/commands/change_points/unmark.py.
"""
import unittest

import click.testing
from mock import MagicMock, patch

from signal_processing.change_points_cli import cli

NS = 'signal_processing.commands.change_points.unmark'


def ns(relative_name):  # pylint: disable=invalid-name
    """Return a full name from a name relative to the tested module's name space."""
    return NS + '.' + relative_name


class TestUnmark(unittest.TestCase):
    """
    Test unmark command.
    """

    def setUp(self):
        self.runner = click.testing.CliRunner()

    def test_unmark_requires_some_params(self):
        """ Test mark requires parameters. """
        result = self.runner.invoke(cli, ['unmark'])
        self.assertEqual(result.exit_code, 2)

    def _test_unmark(self, processed_type=None, expected=None):
        """ test helper. """
        #  patch('signal_processing.change_points.unmark.unmark_change_points',

        with patch(ns('helpers.process_excludes'), autospec=True) as mock_process_excludes, \
            patch(ns('unmark.unmark_change_points'), autospec=True) as mock_unmark, \
            patch(ns('helpers.process_params'), autospec=True) as mock_process_params, \
            patch('signal_processing.commands.helpers.CommandConfiguration', autospec=True) as mock_config:

            expected_query = {'find': 'me'}
            mock_process_params.return_value = expected_query
            expected_excludes = 'exclude me'
            mock_process_excludes.return_value = expected_excludes

            expected_config = MagicMock(name='config', debug=0, log_file='/tmp/log_file')
            mock_config.return_value = expected_config

            params = ['unmark', 'badf', 'sys-perf']
            if processed_type:
                params.append('--processed-type')
                params.append(processed_type)
            result = self.runner.invoke(cli, params)
            self.assertEqual(result.exit_code, 0)
            mock_process_params.assert_called_once_with(
                'sys-perf', None, None, None, revision='badf', thread_level=None)
            mock_process_excludes.assert_called_once_with(())
            mock_unmark.assert_called_once_with(expected, expected_query, expected_excludes,
                                                expected_config)

    def test_unmark_default(self):
        """ Test unmark. """
        self._test_unmark()

    def test_unmark_any(self):
        """ Test unmark any. """
        self._test_unmark('any', None)

    def test_unmark_hidden(self):
        """ Test unmark hidden. """
        self._test_unmark('hidden', 'hidden')

    def test_unmark_acknowledged(self):
        """ Test unmark acknowledged. """
        self._test_unmark('acknowledged', 'acknowledged')
