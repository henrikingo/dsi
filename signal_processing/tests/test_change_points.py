"""
Unit tests for signal_processing/change_points.py.
"""
import time
import unittest

from datetime import datetime

import mock
from mock import MagicMock, patch, mock_open

# pylint: disable=invalid-name
from click.testing import CliRunner
from signal_processing.commands import compute

from signal_processing.change_points import cli
import signal_processing.commands.helpers as helpers
import signal_processing.commands.jobs as jobs


class ClickTest(unittest.TestCase):
    """
    Test Cli group command.
    """

    def setUp(self):
        self.runner = CliRunner()


class TestCli(ClickTest):
    """
    Test Cli group command.
    """

    def test_cli(self):
        """ Test group. """
        result = self.runner.invoke(cli)
        self.assertEqual(result.exit_code, 0)


class TestHelp(ClickTest):
    """
    Test help command.
    """

    def test_help_no_params(self):
        """ Test help with no parameters. """
        result = self.runner.invoke(cli)
        self.assertEqual(result.exit_code, 0)
        self.assertTrue(result.output.startswith("Usage"))

    def test_help_argument(self):
        """ Test help with the `help` argument. """
        result = self.runner.invoke(cli, ['help'])
        self.assertEqual(result.exit_code, 0)
        self.assertTrue(result.output.startswith("Usage"))

    def test_help_help_option(self):
        """ Test help with the `--help` option. """
        result = self.runner.invoke(cli, ['--help'])
        self.assertEqual(result.exit_code, 0)
        self.assertTrue(result.output.startswith("Usage"))

    def test_help_h_option(self):
        """ Test help with the `-h` option. """
        result = self.runner.invoke(cli, ['-h'])
        self.assertEqual(result.exit_code, 0)
        self.assertTrue(result.output.startswith("Usage"))


class TestMark(ClickTest):
    """
    Test mark command.
    """

    def test_mark_requires_some_params(self):
        """ Test mark requires parameters. """
        result = self.runner.invoke(cli, ['mark'])
        self.assertEqual(result.exit_code, 2)

    @patch('signal_processing.change_points.helpers.process_excludes', autospec=True)
    @patch('signal_processing.change_points.mark.mark_change_points', autospec=True)
    @patch('signal_processing.change_points.helpers.process_params', autospec=True)
    @patch('signal_processing.change_points.helpers.CommandConfiguration', autospec=True)
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
        mock_process_params.assert_called_once_with('badf', 'sys-perf', None, None, None, None)
        mock_process_excludes.assert_called_once_with(())
        mock_mark.assert_called_once_with(helpers.PROCESSED_TYPE_ACKNOWLEDGED, expected_query,
                                          expected_excludes, expected_config)

    @patch('signal_processing.change_points.helpers.process_excludes', autospec=True)
    @patch('signal_processing.change_points.mark.mark_change_points', autospec=True)
    @patch('signal_processing.change_points.helpers.process_params', autospec=True)
    @patch('signal_processing.change_points.helpers.CommandConfiguration', autospec=True)
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
        mock_process_params.assert_called_once_with('badf', 'sys-perf', 'linux-standalone',
                                                    'industry_benchmarks', 'ycsb_load', '1')
        mock_process_excludes.assert_called_once_with(('fio', ))
        mock_mark.assert_called_once_with(helpers.PROCESSED_TYPE_ACKNOWLEDGED, expected_query,
                                          expected_excludes, expected_config)


class TestUnmark(ClickTest):
    """
    Test unmark command.
    """

    def test_unmark_requires_some_params(self):
        """ Test mark requires parameters. """
        result = self.runner.invoke(cli, ['unmark'])
        self.assertEqual(result.exit_code, 2)

    def _test_unmark(self, processed_type=None, expected=None):
        """ test helper. """
        #  patch('signal_processing.change_points.unmark.unmark_change_points',

        with patch('signal_processing.change_points.helpers.process_excludes',
                   autospec=True) as mock_process_excludes, \
             patch('signal_processing.change_points.unmark.unmark_change_points',
                   autospec=True) as mock_unmark, \
             patch('signal_processing.change_points.helpers.process_params',
                   autospec=True) as mock_process_params, \
             patch('signal_processing.change_points.helpers.CommandConfiguration',
                   autospec=True) as mock_config:

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
            mock_process_params.assert_called_once_with('badf', 'sys-perf', None, None, None, None)
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


class TestHide(ClickTest):
    """
    Test hide command.
    """

    def test_hide_requires_some_params(self):
        """ Test hide requires parameters. """
        result = self.runner.invoke(cli, ['hide'])
        self.assertEqual(result.exit_code, 2)

    @patch('signal_processing.change_points.helpers.process_excludes', autospec=True)
    @patch('signal_processing.change_points.mark.mark_change_points', autospec=True)
    @patch('signal_processing.change_points.helpers.process_params', autospec=True)
    @patch('signal_processing.change_points.helpers.CommandConfiguration', autospec=True)
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
        mock_process_params.assert_called_once_with('badf', 'sys-perf', None, None, None, None)
        mock_process_excludes.assert_called_once_with(())
        mock_mark.assert_called_once_with(helpers.PROCESSED_TYPE_HIDDEN, expected_query,
                                          expected_excludes, expected_config)

    @patch('signal_processing.change_points.helpers.process_excludes', autospec=True)
    @patch('signal_processing.change_points.mark.mark_change_points', autospec=True)
    @patch('signal_processing.change_points.helpers.process_params', autospec=True)
    @patch('signal_processing.change_points.helpers.CommandConfiguration', autospec=True)
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
        mock_process_params.assert_called_once_with('badf', 'sys-perf', 'linux-standalone',
                                                    'industry_benchmarks', 'ycsb_load', '1')
        mock_process_excludes.assert_called_once_with(('fio', ))
        mock_mark.assert_called_once_with(helpers.PROCESSED_TYPE_HIDDEN, expected_query,
                                          expected_excludes, expected_config)


class TestUpdate(ClickTest):
    """
    Test update command.
    """

    def test_update_requires_some_params(self):
        """ Test update requires parameters. """
        result = self.runner.invoke(cli, ['update'])
        self.assertEqual(result.exit_code, 2)

    @patch('signal_processing.change_points.helpers.process_excludes', autospec=True)
    @patch('signal_processing.change_points.update.update_change_points', autospec=True)
    @patch('signal_processing.change_points.helpers.process_params', autospec=True)
    @patch('signal_processing.change_points.helpers.CommandConfiguration', autospec=True)
    def test_update(self, mock_config, mock_process_params, mock_update, mock_process_excludes):
        """ Test udpate. """
        expected_query = {'find': 'me'}
        mock_process_params.return_value = expected_query
        expected_excludes = 'exclude me'
        mock_process_excludes.return_value = expected_excludes
        expected_config = MagicMock(name='config', debug=0, log_file='/tmp/log_file')
        mock_config.return_value = expected_config

        result = self.runner.invoke(cli, ['update', 'badf', 'sys-perf'])
        self.assertEqual(result.exit_code, 0)
        mock_process_params.assert_called_once_with('badf', 'sys-perf', None, None, None, None)
        mock_process_excludes.assert_called_once_with(())
        # Defaults `processed_type` to hidden.
        mock_update.assert_called_once_with(helpers.PROCESSED_TYPE_HIDDEN, expected_query,
                                            expected_excludes, expected_config)

    @patch('signal_processing.change_points.helpers.process_excludes', autospec=True)
    @patch('signal_processing.change_points.update.update_change_points', autospec=True)
    @patch('signal_processing.change_points.helpers.process_params', autospec=True)
    @patch('signal_processing.change_points.helpers.CommandConfiguration', autospec=True)
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
        mock_process_params.assert_called_once_with('badf', 'sys-perf', 'linux-standalone',
                                                    'industry_benchmarks', 'ycsb_load', '1')
        mock_process_excludes.assert_called_once_with(('fio', ))
        mock_update.assert_called_once_with(helpers.PROCESSED_TYPE_ACKNOWLEDGED, expected_query,
                                            expected_excludes, expected_config)

    @patch('signal_processing.change_points.update.update_change_points', autospec=True)
    @patch('signal_processing.change_points.helpers', autospec=True)
    def test_update_type(self, mock_helpers, mock_update_change_points):
        """ Test update correctly checks `processed-type` type. """
        expected_config = MagicMock(name='config', debug=0, log_file='/tmp/log_file')
        mock_helpers.CommandConfiguration.return_value = expected_config
        result = self.runner.invoke(cli, [
            'update', 'badf', 'sys-perf', 'linux-standalone', 'industry_benchmarks', 'ycsb_load',
            '1', '--exclude', 'fio', '--processed-type', 'incorrect type'
        ])
        self.assertEqual(result.exit_code, 2)


class TestList(ClickTest):
    """
    Test list command.
    """

    @patch('signal_processing.change_points.list_change_points', autospec=True)
    def test_list_check_return(self, mock_list):
        """ Test list with no parameters. """
        result = self.runner.invoke(cli, ['list'])
        self.assertEqual(result.exit_code, 0)

    @patch('signal_processing.change_points.list_change_points', autospec=True)
    def test_list_check_defaults(self, mock_list):
        """ Test list check default parameters. """
        self.runner.invoke(cli, ['list'])
        mock_list.list_change_points.assert_called_once()
        _, kwargs = mock_list.list_change_points.call_args
        self.assertEquals(
            kwargs, {
                'change_point_type': 'unprocessed',
                'query': {},
                'limit': 10,
                'no_older_than': 14,
                'human_readable': True,
                'hide_canaries': True,
                'hide_wtdevelop': True,
                'exclude_patterns': [],
                'command_config': mock.ANY,
                'processed_types': ('acknowledged', )
            })

    @patch('signal_processing.change_points.helpers.process_excludes', autospec=True)
    @patch('signal_processing.change_points.list_change_points', autospec=True)
    def test_list_excludes(self, mock_list, mock_process_excludes):
        """ Test list --exclude. """
        mock_process_excludes.return_value = 'excludes'
        self.runner.invoke(cli, ['list', '--exclude', 'pattern'])
        mock_process_excludes.assert_called_once_with(('pattern', ))
        mock_list.list_change_points.assert_called_once()
        _, kwargs = mock_list.list_change_points.call_args
        self.assertEquals(kwargs['exclude_patterns'], 'excludes')

    @patch('signal_processing.change_points.helpers.process_excludes', autospec=True)
    @patch('signal_processing.change_points.list_change_points', autospec=True)
    def test_list_multiple_excludes(self, mock_list, mock_process_excludes):
        """ Test list --exclude. """
        mock_process_excludes.return_value = 'excludes'
        self.runner.invoke(cli, ['list', '--exclude', 'pattern1', '--exclude', 'pattern2'])
        mock_process_excludes.assert_called_once_with((
            'pattern1',
            'pattern2',
        ))
        mock_list.list_change_points.assert_called_once()
        _, kwargs = mock_list.list_change_points.call_args
        self.assertEquals(kwargs['exclude_patterns'], 'excludes')

    @patch('signal_processing.change_points.list_change_points', autospec=True)
    def test_list_unprocessed(self, mock_list):
        """ Test list unprocessed. """
        result = self.runner.invoke(cli, ['list', '--point-type', 'unprocessed'])
        mock_list.list_change_points.assert_called_once()
        _, kwargs = mock_list.list_change_points.call_args
        self.assertEquals(kwargs['change_point_type'], 'unprocessed')
        self.assertEqual(result.exit_code, 0)

    @patch('signal_processing.change_points.list_change_points', autospec=True)
    def test_list_processed(self, mock_list):
        """ Test list processed. """
        result = self.runner.invoke(cli, ['list', '--point-type', 'processed'])
        mock_list.list_change_points.assert_called_once()
        _, kwargs = mock_list.list_change_points.call_args
        self.assertEquals(kwargs['change_point_type'], 'processed')
        self.assertEqual(result.exit_code, 0)

    @patch('signal_processing.change_points.list_change_points', autospec=True)
    def test_list_raw(self, mock_list):
        """ Test list raw. """
        result = self.runner.invoke(cli, ['list', '--point-type', 'raw'])
        mock_list.list_change_points.assert_called_once()
        _, kwargs = mock_list.list_change_points.call_args
        self.assertEquals(kwargs['change_point_type'], 'raw')
        self.assertEqual(result.exit_code, 0)

    @patch('signal_processing.change_points.list_change_points', autospec=True)
    def test_list_invalid(self, mock_list):
        """ Test list invalid. """
        result = self.runner.invoke(cli, ['list', '--point-type', 'war'])
        self.assertEqual(result.exit_code, 2)

    @patch('signal_processing.change_points.list_change_points', autospec=True)
    def test_list_limit(self, mock_list):
        """ Test list check --limit 10. """
        self.runner.invoke(cli, ['list', '--limit', '10'])
        mock_list.list_change_points.assert_called_once()
        _, kwargs = mock_list.list_change_points.call_args
        self.assertEquals(kwargs['limit'], 10)

    @patch('signal_processing.change_points.list_change_points', autospec=True)
    def test_list_limit_none(self, mock_list):
        """ Test list check --limit None. """
        self.runner.invoke(cli, ['list', '--limit', 'None'])
        mock_list.list_change_points.assert_called_once()
        _, kwargs = mock_list.list_change_points.call_args
        self.assertIsNone(kwargs['limit'])

    @patch('signal_processing.change_points.list_change_points', autospec=True)
    def test_list_no_older(self, mock_list):
        """ Test list check --non-older-than 1. """
        self.runner.invoke(cli, ['list', '--no-older-than', '1'])
        mock_list.list_change_points.assert_called_once()
        _, kwargs = mock_list.list_change_points.call_args
        self.assertEquals(kwargs['no_older_than'], 1)

    @patch('signal_processing.change_points.list_change_points', autospec=True)
    def test_list_no_older_none(self, mock_list):
        """ Test list check --non-older-than None. """
        self.runner.invoke(cli, ['list', '--no-older-than', 'None'])
        mock_list.list_change_points.assert_called_once()
        _, kwargs = mock_list.list_change_points.call_args
        self.assertEquals(kwargs['no_older_than'], None)

    @patch('signal_processing.change_points.list_change_points', autospec=True)
    def test_list_human_readable(self, mock_list):
        """ Test list check --no-human-readable. """
        self.runner.invoke(cli, ['list', '--human-readable'])
        mock_list.list_change_points.assert_called_once()
        _, kwargs = mock_list.list_change_points.call_args
        self.assertEquals(kwargs['human_readable'], True)

    @patch('signal_processing.change_points.list_change_points', autospec=True)
    def test_list_no_human_readable(self, mock_list):
        """ Test list check --no-human-readable. """
        self.runner.invoke(cli, ['list', '--no-human-readable'])
        mock_list.list_change_points.assert_called_once()
        _, kwargs = mock_list.list_change_points.call_args
        self.assertEquals(kwargs['human_readable'], False)

    @patch('signal_processing.change_points.list_change_points', autospec=True)
    def test_list_show_canaries(self, mock_list):
        """ Test list check --show-canaries. """
        self.runner.invoke(cli, ['list', '--show-canaries'])
        mock_list.list_change_points.assert_called_once()
        _, kwargs = mock_list.list_change_points.call_args
        self.assertEquals(kwargs['hide_canaries'], False)

    @patch('signal_processing.change_points.list_change_points', autospec=True)
    def test_list_hide_canaries(self, mock_list):
        """ Test list check --hide-canaries. """
        self.runner.invoke(cli, ['list', '--hide-canaries'])
        mock_list.list_change_points.assert_called_once()
        _, kwargs = mock_list.list_change_points.call_args
        self.assertEquals(kwargs['hide_canaries'], True)

    @patch('signal_processing.change_points.list_change_points', autospec=True)
    def test_list_show_wtdevelop(self, mock_list):
        """ Test list check --show-wtdevelop. """
        self.runner.invoke(cli, ['list', '--show-wtdevelop'])
        mock_list.list_change_points.assert_called_once()
        _, kwargs = mock_list.list_change_points.call_args
        self.assertEquals(kwargs['hide_wtdevelop'], False)

    @patch('signal_processing.change_points.list_change_points', autospec=True)
    def test_list_hide_wtdevelop(self, mock_list):
        """ Test list check --hide-wtdevelop. """
        self.runner.invoke(cli, ['list', '--hide-wtdevelop'])
        mock_list.list_change_points.assert_called_once()
        _, kwargs = mock_list.list_change_points.call_args
        self.assertEquals(kwargs['hide_wtdevelop'], True)


class TestCompute(ClickTest):
    """
    Test compute command.
    """

    def test_compute_requires_params(self):
        """ Test compute with no parameters. """

        result = self.runner.invoke(cli, ['compute'])
        self.assertEqual(result.exit_code, 2)

    @patch('signal_processing.change_points.jobs.process_jobs', autospec=True)
    @patch('signal_processing.change_points.helpers.CommandConfiguration', autospec=True)
    def test_compute(self, mock_command_config_cls, mock_process_jobs):
        """ Test compute. """
        mock_points = MagicMock(name='config')
        mock_points.aggregate.return_value = ()
        expected_config = MagicMock(
            name='config', points=mock_points, debug=0, log_file='/tmp/log_file')
        mock_command_config_cls.return_value = expected_config
        mock_process_jobs.return_value.__enter__.return_value = ()

        result = self.runner.invoke(cli, ['compute', 'sys-perf'])
        self.assertEqual(result.exit_code, 0)

    @patch('signal_processing.change_points.helpers.CommandConfiguration', autospec=True)
    def test_compute_params(self, mock_command_config_cls):
        """ Test compute works with parameters. """

        mock_points = MagicMock(name='config')
        mock_points.aggregate.return_value = ()
        expected_config = MagicMock(
            name='config', points=mock_points, debug=0, log_file='/tmp/log_file')
        mock_command_config_cls.return_value = expected_config

        with patch(
            'signal_processing.change_points.helpers.process_params') as mock_process_params, \
                patch('signal_processing.change_points.jobs.process_jobs') as mock_process_jobs:
            mock_process_jobs.return_value.__enter__.return_value = ()
            result = self.runner.invoke(
                cli,
                ['compute', 'sys-perf', 'linux-standalone', 'industry_benchmarks', 'ycsb_load'])
            self.assertEqual(result.exit_code, 0)
            mock_process_params.assert_called_once_with(None, 'sys-perf', 'linux-standalone',
                                                        'industry_benchmarks', 'ycsb_load', None)

    @patch('signal_processing.change_points.helpers.CommandConfiguration', autospec=True)
    def test_compute_legacy(self, mock_command_config_cls):
        """ Test compute works with legacy. """

        mock_points = MagicMock(name='config')
        mock_points.aggregate.return_value = ()
        expected_config = MagicMock(
            name='config', points=mock_points, debug=0, log_file='/tmp/log_file')
        mock_command_config_cls.return_value = expected_config

        with patch(
            'signal_processing.change_points.helpers.filter_legacy_tasks')\
            as mock_filter_legacy_tasks, \
                patch('signal_processing.change_points.jobs.process_jobs') as mock_process_jobs:
            mock_process_jobs.return_value.__enter__.return_value = ()

            result = self.runner.invoke(cli, ['compute', 'sys-perf', '--legacy'])
            self.assertEqual(result.exit_code, 0)
            mock_filter_legacy_tasks.assert_not_called()

    @patch('signal_processing.change_points.helpers.CommandConfiguration', autospec=True)
    def test_compute_no_legacy(self, mock_command_config_cls):
        """ Test compute works without legacy. """

        mock_points = MagicMock(name='config')
        mock_points.aggregate.return_value = ()
        expected_config = MagicMock(
            name='config', points=mock_points, debug=0, log_file='/tmp/log_file')
        mock_command_config_cls.return_value = expected_config

        with patch(
            'signal_processing.change_points.helpers.filter_legacy_tasks')\
                as mock_filter_legacy_tasks, \
                patch('signal_processing.change_points.jobs.process_jobs') as mock_process_jobs:
            mock_process_jobs.return_value.__enter__.return_value = ()

            result = self.runner.invoke(cli, ['compute', 'sys-perf'])
            self.assertEqual(result.exit_code, 0)
            mock_filter_legacy_tasks.assert_called_once_with(mock.ANY)

    @patch('signal_processing.change_points.helpers.CommandConfiguration', autospec=True)
    def test_compute_pool_size(self, mock_command_config_cls):
        """ Test compute works with pool_size. """

        mock_points = MagicMock(name='config')
        mock_points.aggregate.return_value = ()
        expected_config = MagicMock(
            name='config', points=mock_points, debug=0, log_file='/tmp/log_file')
        mock_command_config_cls.return_value = expected_config
        pool_size = 2
        with patch('signal_processing.change_points.jobs.process_jobs') as mock_process_jobs:
            mock_process_jobs.return_value.__enter__.return_value = ()

            result = self.runner.invoke(cli, ['compute', 'sys-perf', '--pool-size', str(pool_size)])
            self.assertEqual(result.exit_code, 0)
            _, kwargs = mock_process_jobs.call_args
            self.assertEquals(kwargs['pool_size'], pool_size)

    @patch('signal_processing.change_points.helpers.CommandConfiguration', autospec=True)
    def test_compute_weighting(self, mock_command_config_cls):
        """ Test compute works with weighting. """

        mock_points = MagicMock(name='config')
        mock_points.aggregate.return_value = ()
        expected_config = MagicMock(
            name='config', points=mock_points, debug=0, log_file='/tmp/log_file')
        mock_command_config_cls.return_value = expected_config

        with patch('signal_processing.change_points.jobs.process_jobs') as mock_process_jobs:
            mock_process_jobs.return_value.__enter__.return_value = ()

            result = self.runner.invoke(cli, ['compute', 'sys-perf', '--weighting', '.002'])
            self.assertEqual(result.exit_code, 0)

    @patch('signal_processing.change_points.helpers.CommandConfiguration', autospec=True)
    def test_compute_excludes(self, mock_command_config_cls):
        """ Test compute works with excludes. """

        mock_points = MagicMock(name='config')
        mock_points.aggregate.return_value = ()
        expected_config = MagicMock(
            name='config', points=mock_points, debug=0, log_file='/tmp/log_file')
        mock_command_config_cls.return_value = expected_config

        with patch(
            'signal_processing.change_points.helpers.process_excludes')\
                as mock_process_excludes, \
                patch('signal_processing.change_points.jobs.process_jobs') as mock_process_jobs:
            mock_process_jobs.return_value.__enter__.return_value = ()

            result = self.runner.invoke(cli, ['compute', 'sys-perf', '--exclude', 'fio'])
            self.assertEqual(result.exit_code, 0)
            mock_process_excludes.assert_called_once_with(('fio', ))

    @patch('signal_processing.change_points.helpers.CommandConfiguration', autospec=True)
    def test_compute_no_excludes(self, mock_command_config_cls):
        """ Test compute works without excludes. """

        mock_points = MagicMock(name='config')
        mock_points.aggregate.return_value = ()
        expected_config = MagicMock(
            name='config', points=mock_points, debug=0, log_file='/tmp/log_file')
        mock_command_config_cls.return_value = expected_config

        with patch(
            'signal_processing.change_points.helpers.process_excludes')\
                as mock_process_excludes, \
                patch('signal_processing.change_points.jobs.process_jobs') as mock_process_jobs:
            mock_process_jobs.return_value.__enter__.return_value = ()

            result = self.runner.invoke(cli, ['compute', 'sys-perf'])
            self.assertEqual(result.exit_code, 0)
            mock_process_excludes.assert_called_once_with(())

    @patch('signal_processing.change_points.helpers.CommandConfiguration', autospec=True)
    def test_compute_progress_bar(self, mock_command_config_cls):
        """ Test compute uses the `--progressbar` flag correctly. """

        mock_points = MagicMock(name='config')
        mock_points.aggregate.return_value = ()
        expected_config = MagicMock(
            name='config', points=mock_points, debug=0, log_file='/tmp/log_file')
        mock_command_config_cls.return_value = expected_config

        # Defaults to `--progressbar`.
        with patch('signal_processing.change_points.jobs.process_jobs') as mock_process_jobs:
            mock_process_jobs.return_value.__enter__.return_value = ()

            result = self.runner.invoke(cli, ['compute', 'sys-perf'])
            self.assertEqual(result.exit_code, 0)
            _, kwargs = mock_process_jobs.call_args
            self.assertTrue(kwargs['progressbar'])

        with patch('signal_processing.change_points.jobs.process_jobs') as mock_process_jobs:
            mock_process_jobs.return_value.__enter__.return_value = ()

            result = self.runner.invoke(cli, ['compute', 'sys-perf', '--progressbar'])
            self.assertEqual(result.exit_code, 0)
            _, kwargs = mock_process_jobs.call_args
            self.assertTrue(kwargs['progressbar'])

        with patch('signal_processing.change_points.jobs.process_jobs') as mock_process_jobs:
            mock_process_jobs.return_value.__enter__.return_value = ()

            result = self.runner.invoke(cli, ['compute', 'sys-perf', '--no-progressbar'])
            self.assertEqual(result.exit_code, 0)
            _, kwargs = mock_process_jobs.call_args
            self.assertFalse(kwargs['progressbar'])

    @patch('signal_processing.change_points.helpers.CommandConfiguration', autospec=True)
    def test_compute_creates_jobs(self, mock_command_config_cls):
        """ Test compute creates jobs. """

        mock_points = MagicMock(name='config')
        mock_points.aggregate.return_value = ()
        expected_config = MagicMock(
            name='config', points=mock_points, debug=0, log_file='/tmp/log_file')
        mock_command_config_cls.return_value = expected_config

        with patch(
            'signal_processing.change_points.helpers.generate_tests') as mock_generate_tests, \
                patch('signal_processing.change_points.jobs.process_jobs') as mock_process_jobs,\
                patch('signal_processing.change_points.jobs.Job') as mock_job_cls:
            mock_process_jobs.return_value.__enter__.return_value = ()

            test_identifiers = [{'test': str(i)} for i in range(5)]
            mock_generate_tests.return_value = test_identifiers

            result = self.runner.invoke(cli, ['compute', 'sys-perf'])
            self.assertEqual(result.exit_code, 0)
            mock_job_cls.assert_has_calls([
                mock.call(
                    compute.compute_change_points,
                    arguments=(test_identifier, .001, expected_config),
                    identifier=test_identifier) for test_identifier in test_identifiers
            ])

    @patch('signal_processing.change_points.helpers.CommandConfiguration', autospec=True)
    def test_compute_jobs(self, mock_command_config_cls):
        """ Test compute job iteration. """

        mock_points = MagicMock(name='config')
        mock_points.aggregate.return_value = ()
        expected_config = MagicMock(
            name='config', points=mock_points, debug=0, log_file='/tmp/log_file')
        mock_command_config_cls.return_value = expected_config

        with patch('signal_processing.change_points.jobs.process_jobs') as mock_process_jobs:
            mock_job = MagicMock(name='job', exception=None, identifier={'test': 'name'})
            mock_process_jobs.return_value.__enter__.return_value = [mock_job]
            result = self.runner.invoke(cli, ['compute', 'sys-perf'])
            self.assertEqual(result.exit_code, 0)

    @patch('signal_processing.change_points.helpers.CommandConfiguration', autospec=True)
    def test_compute_exceptions(self, mock_command_config_cls):
        """ Test compute exceptions. """

        mock_points = MagicMock(name='config')
        mock_points.aggregate.return_value = ()
        expected_config = MagicMock(
            name='config', points=mock_points, debug=0, log_file='/tmp/log_file')
        mock_command_config_cls.return_value = expected_config

        with patch('signal_processing.change_points.jobs.process_jobs') as mock_process_jobs:
            job_list = [jobs.Job(time.sleep, arguments=(0.0, )) for _ in range(3)]
            for i, job in enumerate(job_list):
                job.started_at = datetime.utcnow()
                job.ended_at = datetime.utcnow()
                job.identifier = {'test': 'identifier{}'.format(i)}
                if i == 0:
                    job.exception = None
                    job.status = 'status'
                else:
                    job.exception = Exception(str(i))
                    job.status = 'status {}'.format(i)
            mock_process_jobs.return_value = job_list
            result = self.runner.invoke(cli, ['compute', 'sys-perf'])
            self.assertEqual(result.exit_code, 2)


class TestManage(ClickTest):
    """
    Test manage command.
    """

    @patch('signal_processing.change_points.manage.manage', autospec=True)
    @patch('signal_processing.change_points.helpers.CommandConfiguration', autospec=True)
    def test_manage(self, mock_config, mock_manage):
        """ Test manage. """
        expected_config = MagicMock(name='config', debug=0, log_file='/tmp/log_file')
        mock_config.return_value = expected_config

        result = self.runner.invoke(cli, ['manage'])
        self.assertEqual(result.exit_code, 0)
        mock_manage.assert_called_once_with(expected_config)


class TestVisualize(ClickTest):
    """
    Test visualize command.
    """

    @unittest.skip("test_visualize_no_params fails in evergreen")
    @patch('signal_processing.change_points.visualize', autospec=True)
    @patch('signal_processing.change_points.helpers.CommandConfiguration', style=['bmh'])
    def test_visualize_no_params(self, mock_config, mock_visualize):
        """ Test visualize with no parameters. """

        result = self.runner.invoke(cli, ['visualize'])
        self.assertEqual(result.exit_code, 0)


class TestListBuildFailures(ClickTest):
    """
    Test list-build-failures command.
    """

    @patch('signal_processing.change_points.list_build_failures.list_build_failures', autospec=True)
    @patch('signal_processing.change_points.helpers.CommandConfiguration', autospec=True)
    def test_list_build_failures_no_params(self, mock_config, mock_list_build_failures):
        """ Test list-build-failures requires parameters. """
        expected_config = MagicMock(name='config', debug=0, log_file='/tmp/log_file')
        mock_config.return_value = expected_config
        result = self.runner.invoke(cli, ['list-build-failures'])
        self.assertEqual(result.exit_code, 2)

    @patch('signal_processing.change_points.helpers.process_excludes', autospec=True)
    @patch('signal_processing.change_points.list_build_failures.list_build_failures', autospec=True)
    @patch('signal_processing.change_points.helpers.process_params', autospec=True)
    @patch('signal_processing.change_points.helpers.CommandConfiguration', autospec=True)
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
        mock_process_params.assert_called_once_with('badf', 'sys-perf', None, None, None, None)
        # Defaults `human_readable` to False.
        mock_list_build_failures.assert_called_once_with(expected_query, False, expected_config)

    @patch('signal_processing.change_points.helpers.process_excludes', autospec=True)
    @patch('signal_processing.change_points.list_build_failures.list_build_failures', autospec=True)
    @patch('signal_processing.change_points.helpers.process_params', autospec=True)
    @patch('signal_processing.change_points.helpers.CommandConfiguration', autospec=True)
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
        mock_process_params.assert_called_once_with('badf', 'sys-perf', 'linux-standalone',
                                                    'industry_benchmarks', 'ycsb_load', None)
        self.assertEqual(result.exit_code, 0)
        mock_list_build_failures.assert_called_once_with(expected_query, True, expected_config)


class TestListfailures(ClickTest):
    """
    Test failures command.
    """

    @patch('signal_processing.change_points.list_build_failures.list_build_failures', autospec=True)
    @patch('signal_processing.change_points.helpers.CommandConfiguration', autospec=True)
    def test_no_params(self, mock_config, mock_list_build_failures):
        """ Test failures requires parameters. """
        expected_config = MagicMock(name='config', debug=0, log_file='/tmp/log_file')
        mock_config.return_value = expected_config
        result = self.runner.invoke(cli, ['failures'])
        self.assertEqual(result.exit_code, 2)

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
        with patch('signal_processing.change_points.open', mock_open(read_data='{client:[]}'))\
             as m, \
             patch('signal_processing.change_points.list_failures.list_failures', autospec=True)\
             as mock_failures,\
             patch('signal_processing.change_points.helpers.CommandConfiguration', autospec=True)\
             as mock_config,\
             patch('signal_processing.change_points.os.path.expanduser') as mock_expanduser,\
             patch('signal_processing.change_points.evergreen_client.Client') as mock_client:

            expected_config = MagicMock(name='config', debug=0, log_file='/tmp/log_file')
            mock_config.return_value = expected_config
            mock_expanduser.return_value = '/HOME/evergreen.yml'

            mock_evg_client = MagicMock(name='evg_client')
            mock_client.return_value = mock_evg_client
            result = self.runner.invoke(cli, command)
            self.assertEqual(result.exit_code, 0)

            m.assert_called_once_with('/HOME/evergreen.yml')
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
