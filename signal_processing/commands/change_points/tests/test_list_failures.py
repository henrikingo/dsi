"""
Unit tests for signal_processing/commands/change_points/list_failures.py.
"""
import unittest

import click.testing
from mock import MagicMock, patch, mock_open

from signal_processing.change_points_cli import cli

NS = 'signal_processing.commands.change_points.list_failures'


def ns(relative_name):  # pylint: disable=invalid-name
    """Return a full name from a name relative to the tested module's name space."""
    return NS + '.' + relative_name


class TestListFailures(unittest.TestCase):
    """
    Test failures command.
    """

    def setUp(self):
        self.runner = click.testing.CliRunner()

    @patch('signal_processing.commands.helpers.CommandConfiguration', autospec=True)
    def test_no_params(self, mock_config):
        """ Test failures requires parameters. """
        expected_config = MagicMock(name='config', debug=0, log_file='/tmp/log_file')
        mock_config.return_value = expected_config
        result = self.runner.invoke(cli, ['failures'])
        self.assertEqual(result.exit_code, 2)

    # pylint: disable=too-many-arguments
    def _test_list_failures(self,
                            command,
                            project='sys-perf',
                            human_readable=True,
                            limit=None,
                            no_older_than=14,
                            show_wtdevelop=False,
                            show_patches=False,
                            evergreen_config='~/.evergreen.yml'):
        """ test helper function. """
        # pylint: disable=too-many-locals
        with patch(ns('open'), mock_open(read_data='{client:[]}')) as m_open, \
             patch(ns('list_failures.list_failures'), autospec=True) as mock_failures, \
             patch('signal_processing.commands.helpers.CommandConfiguration', autospec=True) as mock_config, \
             patch(ns('os.path.expanduser')) as mock_expanduser, \
             patch(ns('evergreen_client.Client')) as mock_client:

            expected_config = MagicMock(name='config', debug=0, log_file='/tmp/log_file')
            mock_config.return_value = expected_config
            mock_expanduser.return_value = '/HOME/evergreen.yml'

            mock_evg_client = MagicMock(name='evg_client')
            mock_client.return_value = mock_evg_client
            result = self.runner.invoke(cli, command)
            self.assertEqual(result.exit_code, 0)

            m_open.assert_called_once_with('/HOME/evergreen.yml')
            mock_client.assert_called_once_with({'client': []})
            mock_expanduser.assert_called_once_with(evergreen_config)

            mock_failures.assert_called_once_with(project, show_wtdevelop, show_patches,
                                                  human_readable, limit, no_older_than,
                                                  mock_evg_client, expected_config)

    def test_list_failures(self):
        """ Test failures defaults params. """
        command = ['failures', 'sys-perf']
        self._test_list_failures(command)

    def test_list_failures_show_params(self):
        """ Test failures params. """
        command = [
            'failures', 'sys-perf', '--no-human-readable', '--limit', '1', '--no-older-than', '7',
            '--show-wtdevelop', '--show-patches', '--evergreen-config', './.evergreen.yml'
        ]
        self._test_list_failures(
            command,
            project='sys-perf',
            human_readable=False,
            limit=1,
            no_older_than=7,
            show_wtdevelop=True,
            show_patches=True,
            evergreen_config='./.evergreen.yml')

    def test_list_failures_hide_params(self):
        """ Test failures params. """
        command = [
            'failures', 'sys-perf', '--no-human-readable', '--limit', '1', '--no-older-than', '7',
            '--hide-wtdevelop', '--hide-patches'
        ]
        self._test_list_failures(
            command, project='sys-perf', human_readable=False, limit=1, no_older_than=7)
