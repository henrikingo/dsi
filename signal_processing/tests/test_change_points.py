"""
Unit tests for signal_processing/change_points.py.
"""
import multiprocessing
import unittest

from StringIO import StringIO
import mock
from mock import MagicMock, call, patch

# pylint: disable=invalid-name
from click.testing import CliRunner

from signal_processing.change_points import cli
import signal_processing.commands.helpers as helpers


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
        """ Test mark requires params. """
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


class TestHide(ClickTest):
    """
    Test hide command.
    """

    def test_hide_requires_some_params(self):
        """ Test hide requires params. """
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
        """ Test update requires some params. """
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
        """ Test list with no params. """
        result = self.runner.invoke(cli, ['list'])
        self.assertEqual(result.exit_code, 0)

    @patch('signal_processing.change_points.list_change_points', autospec=True)
    def test_list_check_defaults(self, mock_list):
        """ Test list check default params. """
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
                'command_config': mock.ANY
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

    @patch('signal_processing.change_points.compute.compute_change_points', autospec=True)
    @patch('signal_processing.change_points.helpers', autospec=True)
    def test_compute_requires_params(self, mock_helpers, mock_compare):
        """ Test compute with no parameters. """

        mock_points = MagicMock(name='config')
        expected_config = MagicMock(
            name='config', style=['bmh'], points=mock_points, debug=0, log_file='/tmp/log_file')
        mock_helpers.CommandConfiguration.return_value = expected_config
        result = self.runner.invoke(cli, ['compute'])
        self.assertEqual(result.exit_code, 2)

    @patch('signal_processing.change_points.compute.compute_change_points', autospec=True)
    @patch('signal_processing.change_points.multiprocessing.Pool', autospec=True)
    @patch('signal_processing.change_points.helpers', autospec=True)
    def test_compute(self, mock_helpers, mock_pool, mock_compute):
        #pylint: disable=too-many-locals
        """ Test compute. """

        expected_query = {'find': 'me'}
        mock_helpers.process_params.return_value = expected_query
        expected_excludes = 'exclude me'
        mock_helpers.process_excludes.return_value = expected_excludes
        mock_points = MagicMock(name='config')
        expected_config = MagicMock(
            name='config', points=mock_points, debug=0, log_file='/tmp/log_file')
        mock_helpers.CommandConfiguration.return_value = expected_config
        expected_tasks = ['task1', 'task2']
        mock_helpers.get_matching_tasks.return_value = expected_tasks
        mock_helpers.filter_legacy_tasks.return_value = expected_tasks
        expected_test_identifiers = [{'test': 'test1'}, {'test': 'test2'}, {'test': 'test3'}]
        mock_helpers.generate_tests.return_value = expected_test_identifiers
        mock_helpers.filter_tests.side_effect = [True, True, True]
        label_width = 20
        bar_width = 20
        info_width = 20
        padding = 20
        mock_helpers.get_bar_widths.return_value = (label_width, bar_width, info_width, padding)
        mock_helpers.get_bar_template.return_value = 'mock_bar_template'

        result = self.runner.invoke(cli, ['compute', 'sys-perf'])
        self.assertEqual(result.exit_code, 0)
        mock_helpers.process_params.assert_called_once_with(None, 'sys-perf', None, None, None,
                                                            None)
        mock_helpers.get_matching_tasks.assert_called_once_with(mock_points, expected_query)
        mock_helpers.filter_legacy_tasks.assert_called_once_with(expected_tasks)
        mock_helpers.process_excludes.assert_called_once_with(())
        mock_helpers.generate_tests.assert_called_once_with(expected_tasks)
        filter_tests_calls = [
            call(test['test'], expected_excludes) for test in expected_test_identifiers
        ]
        mock_helpers.filter_tests.assert_has_calls(filter_tests_calls)
        mock_helpers.get_bar_widths.assert_called_once_with()
        mock_helpers.get_bar_template.assert_called_once_with(label_width, bar_width, info_width)
        # Defaults `pool_size` to `max(multiprocessing.cpu_count() - 1, 1))`.
        mock_pool.assert_called_once_with(max(multiprocessing.cpu_count() - 1, 1))
        # Defaults `weighting` to .001.
        thread_calls = ((mock_compute, test_identifier, .001, expected_config)
                        for test_identifier in expected_test_identifiers)
        mock_pool.return_value.imap_unordered.assert_called_once()
        # Work around to assert correct imap call arguments since the generator object is not
        # comparable.
        imap_call = mock_pool.return_value.imap_unordered.call_args
        self.assertEqual(imap_call[0][0], mock_helpers.function_adapter)
        for i, thread_call in enumerate(imap_call[0][1]):
            self.assertEqual(thread_call, thread_calls[i])

    @patch('signal_processing.change_points.compute.compute_change_points', autospec=True)
    @patch('signal_processing.change_points.multiprocessing.Pool', autospec=True)
    @patch('signal_processing.change_points.helpers', autospec=True)
    def test_compute_params(self, mock_helpers, mock_pool, mock_compute):
        #pylint: disable=too-many-locals
        """ Test compute works with parameters. """

        expected_query = {'find': 'me'}
        mock_helpers.process_params.return_value = expected_query
        expected_excludes = 'exclude me'
        mock_helpers.process_excludes.return_value = expected_excludes
        mock_points = MagicMock(name='config')
        expected_config = MagicMock(
            name='config', points=mock_points, debug=0, log_file='/tmp/log_file')
        mock_helpers.CommandConfiguration.return_value = expected_config
        expected_tasks = ['task1', 'task2']
        mock_helpers.get_matching_tasks.return_value = expected_tasks
        mock_helpers.filter_legacy_tasks.return_value = expected_tasks
        expected_test_identifiers = [{'test': 'test1'}, {'test': 'test2'}, {'test': 'test3'}]
        mock_helpers.generate_tests.return_value = expected_test_identifiers
        mock_helpers.filter_tests.side_effect = [True, True, True]
        label_width = 20
        bar_width = 20
        info_width = 20
        padding = 20
        mock_helpers.get_bar_widths.return_value = (label_width, bar_width, info_width, padding)
        mock_helpers.get_bar_template.return_value = 'mock_bar_template'

        result = self.runner.invoke(cli, [
            'compute', 'sys-perf', 'linux-standalone', 'industry_benchmarks', 'ycsb_load',
            '--progressbar', '--legacy', '--pool-size', '2', '--weighting', '.002', '--exclude',
            'fio'
        ])
        self.assertEqual(result.exit_code, 0)
        mock_helpers.process_params.assert_called_once_with(
            None, 'sys-perf', 'linux-standalone', 'industry_benchmarks', 'ycsb_load', None)
        mock_helpers.get_matching_tasks.assert_called_once_with(mock_points, expected_query)
        mock_helpers.filter_legacy_tasks.assert_not_called()
        mock_helpers.process_excludes.assert_called_once_with(('fio', ))
        mock_helpers.generate_tests.assert_called_once_with(expected_tasks)
        filter_tests_calls = [
            call(test['test'], expected_excludes) for test in expected_test_identifiers
        ]
        mock_helpers.filter_tests.assert_has_calls(filter_tests_calls)
        mock_helpers.get_bar_widths.assert_called_once_with()
        mock_helpers.get_bar_template.assert_called_once_with(label_width, bar_width, info_width)
        mock_pool.assert_called_once_with(2)
        thread_calls = ((mock_compute, test_identifier, .002, expected_config)
                        for test_identifier in expected_test_identifiers)
        mock_pool.return_value.imap_unordered.assert_called_once()
        # Work around to assert correct imap call arguments since the generator object is not
        # comparable.
        imap_call = mock_pool.return_value.imap_unordered.call_args
        self.assertEqual(imap_call[0][0], mock_helpers.function_adapter)
        for i, thread_call in enumerate(imap_call[0][1]):
            self.assertEqual(thread_call, thread_calls[i])

        # Check that explicit `--no-legacy` flag works.
        result = self.runner.invoke(cli, ['compute', 'sys-perf', '--no-legacy'])
        self.assertEqual(result.exit_code, 0)
        mock_helpers.filter_legacy_tasks.assert_called_once()

    @patch('signal_processing.change_points.compute.compute_change_points', autospec=True)
    @patch('signal_processing.change_points.helpers')
    def test_compute_progress_bar(self, mock_helpers, mock_compare):
        """ Test compute uses the `--progressbar` flag correctly. """

        progressbar = 'signal_processing.change_points.click.progressbar'
        mock_helpers.CommandConfiguration.return_value = MagicMock(
            name='config', debug=0, log_file='/tmp/log_file')
        mock_helpers.get_bar_widths.return_value = [
            'label_width', 'bar_width', 'info_width', 'padding'
        ]

        # Defaults to `--progressbar`.
        with patch(progressbar, autospec=True) as mock_progressbar:
            result = self.runner.invoke(cli, ['compute', 'sys-perf'])
            self.assertEqual(result.exit_code, 0)
            _, kwargs = mock_progressbar.call_args
            self.assertEqual(kwargs['file'], None)

        with patch(progressbar, autospec=True) as mock_progressbar:
            result = self.runner.invoke(cli, ['compute', 'sys-perf', '--progressbar'])
            self.assertEqual(result.exit_code, 0)
            _, kwargs = mock_progressbar.call_args
            self.assertEqual(kwargs['file'], None)

        with patch(progressbar, autospec=True) as mock_progressbar:
            result = self.runner.invoke(cli, ['compute', 'sys-perf', '--no-progressbar'])
            self.assertEqual(result.exit_code, 0)
            _, kwargs = mock_progressbar.call_args
            self.assertTrue(isinstance(kwargs['file'], StringIO))


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
        """ Test visualize with no params. """

        result = self.runner.invoke(cli, ['visualize'])
        self.assertEqual(result.exit_code, 0)


class TestListBuildFailures(ClickTest):
    """
    Test list-build-failures command.
    """

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

        result = self.runner.invoke(cli, ['list-build-failures'])
        self.assertEqual(result.exit_code, 0)
        mock_process_params.assert_called_once_with(None, None, None, None, None, None)
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