"""
Unit tests for signal_processing/commands/change_points/compute.py.
"""
from datetime import datetime
import time
import unittest

import click.testing
import mock
from mock import MagicMock, patch

import signal_processing.change_points.compute
from signal_processing.change_points_cli import cli
from signal_processing.commands import jobs

NS = 'signal_processing.commands.change_points.compute'


def ns(relative_name):  # pylint: disable=invalid-name
    """Return a full name from a name relative to the tested module's name space."""
    return NS + '.' + relative_name


class TestCompute(unittest.TestCase):
    """
    Test compute command.
    """

    def setUp(self):
        self.runner = click.testing.CliRunner()

    def test_compute_requires_params(self):
        """ Test compute with no parameters. """

        result = self.runner.invoke(cli, ['compute'])
        self.assertEqual(result.exit_code, 2)

    @patch(ns('jobs.process_jobs'), autospec=True)
    @patch('signal_processing.commands.helpers.CommandConfiguration', autospec=True)
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

    @patch('signal_processing.commands.helpers.CommandConfiguration', autospec=True)
    def test_compute_params(self, mock_command_config_cls):
        """ Test compute works with parameters. """

        mock_points = MagicMock(name='config')
        mock_points.aggregate.return_value = ()
        expected_config = MagicMock(
            name='config', points=mock_points, debug=0, log_file='/tmp/log_file')
        mock_command_config_cls.return_value = expected_config

        with patch(ns('helpers.process_params')) as mock_process_params, \
             patch(ns('jobs.process_jobs')) as mock_process_jobs:

            mock_process_jobs.return_value.__enter__.return_value = ()
            result = self.runner.invoke(
                cli,
                ['compute', 'sys-perf', 'linux-standalone', 'industry_benchmarks', 'ycsb_load'])
            self.assertEqual(result.exit_code, 0)
            mock_process_params.assert_called_once_with(
                'sys-perf',
                'linux-standalone',
                'industry_benchmarks',
                'ycsb_load',
                thread_level=None)

    @patch('signal_processing.commands.helpers.CommandConfiguration', autospec=True)
    def test_compute_legacy(self, mock_command_config_cls):
        """ Test compute works with legacy. """

        mock_points = MagicMock(name='config')
        mock_points.aggregate.return_value = ()
        expected_config = MagicMock(
            name='config', points=mock_points, debug=0, log_file='/tmp/log_file')
        mock_command_config_cls.return_value = expected_config

        with patch(ns('helpers.filter_legacy_tasks')) as mock_filter_legacy_tasks, \
             patch(ns('jobs.process_jobs')) as mock_process_jobs:

            mock_process_jobs.return_value.__enter__.return_value = ()

            result = self.runner.invoke(cli, ['compute', 'sys-perf', '--legacy'])
            self.assertEqual(result.exit_code, 0)
            mock_filter_legacy_tasks.assert_not_called()

    @patch('signal_processing.commands.helpers.CommandConfiguration', autospec=True)
    def test_compute_no_legacy(self, mock_command_config_cls):
        """ Test compute works without legacy. """

        mock_points = MagicMock(name='config')
        mock_points.aggregate.return_value = ()
        expected_config = MagicMock(
            name='config', points=mock_points, debug=0, log_file='/tmp/log_file')
        mock_command_config_cls.return_value = expected_config

        with patch(ns('helpers.filter_legacy_tasks')) as mock_filter_legacy_tasks, \
             patch(ns('jobs.process_jobs')) as mock_process_jobs:

            mock_process_jobs.return_value.__enter__.return_value = ()

            result = self.runner.invoke(cli, ['compute', 'sys-perf'])
            self.assertEqual(result.exit_code, 0)
            mock_filter_legacy_tasks.assert_called_once_with(mock.ANY)

    @patch('signal_processing.commands.helpers.CommandConfiguration', autospec=True)
    def test_compute_pool_size(self, mock_command_config_cls):
        """ Test compute works with pool_size. """

        mock_points = MagicMock(name='config')
        mock_points.aggregate.return_value = ()
        expected_config = MagicMock(
            name='config', points=mock_points, debug=0, log_file='/tmp/log_file')
        mock_command_config_cls.return_value = expected_config
        pool_size = 2

        with patch(ns('jobs.process_jobs')) as mock_process_jobs:
            mock_process_jobs.return_value.__enter__.return_value = ()

            result = self.runner.invoke(cli, ['compute', 'sys-perf', '--pool-size', str(pool_size)])
            self.assertEqual(result.exit_code, 0)
            _, kwargs = mock_process_jobs.call_args
            self.assertEquals(kwargs['pool_size'], pool_size)

    @patch('signal_processing.commands.helpers.CommandConfiguration', autospec=True)
    def test_compute_weighting(self, mock_command_config_cls):
        """ Test compute works with weighting. """

        mock_points = MagicMock(name='config')
        mock_points.aggregate.return_value = ()
        expected_config = MagicMock(
            name='config', points=mock_points, debug=0, log_file='/tmp/log_file')
        mock_command_config_cls.return_value = expected_config

        with patch(ns('jobs.process_jobs')) as mock_process_jobs:
            mock_process_jobs.return_value.__enter__.return_value = ()

            result = self.runner.invoke(cli, ['compute', 'sys-perf', '--weighting', '.002'])
            self.assertEqual(result.exit_code, 0)

    @patch('signal_processing.commands.helpers.CommandConfiguration', autospec=True)
    def test_compute_excludes(self, mock_command_config_cls):
        """ Test compute works with excludes. """

        mock_points = MagicMock(name='config')
        mock_points.aggregate.return_value = ()
        expected_config = MagicMock(
            name='config', points=mock_points, debug=0, log_file='/tmp/log_file')
        mock_command_config_cls.return_value = expected_config

        with patch(ns('helpers.process_excludes')) as mock_process_excludes, \
             patch(ns('jobs.process_jobs')) as mock_process_jobs:

            mock_process_jobs.return_value.__enter__.return_value = ()

            result = self.runner.invoke(cli, ['compute', 'sys-perf', '--exclude', 'fio'])
            self.assertEqual(result.exit_code, 0)
            mock_process_excludes.assert_called_once_with(('fio', ))

    @patch('signal_processing.commands.helpers.CommandConfiguration', autospec=True)
    def test_compute_no_excludes(self, mock_command_config_cls):
        """ Test compute works without excludes. """

        mock_points = MagicMock(name='config')
        mock_points.aggregate.return_value = ()
        expected_config = MagicMock(
            name='config', points=mock_points, debug=0, log_file='/tmp/log_file')
        mock_command_config_cls.return_value = expected_config

        with patch(ns('helpers.process_excludes')) as mock_process_excludes, \
             patch(ns('jobs.process_jobs')) as mock_process_jobs:

            mock_process_jobs.return_value.__enter__.return_value = ()

            result = self.runner.invoke(cli, ['compute', 'sys-perf'])
            self.assertEqual(result.exit_code, 0)
            mock_process_excludes.assert_called_once_with(())

    @patch('signal_processing.commands.helpers.CommandConfiguration', autospec=True)
    def test_compute_progress_bar(self, mock_command_config_cls):
        """ Test compute uses the `--progressbar` flag correctly. """

        mock_points = MagicMock(name='config')
        mock_points.aggregate.return_value = ()
        expected_config = MagicMock(
            name='config', points=mock_points, debug=0, log_file='/tmp/log_file')
        mock_command_config_cls.return_value = expected_config

        # Defaults to `--progressbar`.
        with patch(ns('jobs.process_jobs')) as mock_process_jobs:
            mock_process_jobs.return_value.__enter__.return_value = ()

            result = self.runner.invoke(cli, ['compute', 'sys-perf'])
            self.assertEqual(result.exit_code, 0)
            _, kwargs = mock_process_jobs.call_args
            self.assertTrue(kwargs['progressbar'])

        with patch(ns('jobs.process_jobs')) as mock_process_jobs:
            mock_process_jobs.return_value.__enter__.return_value = ()

            result = self.runner.invoke(cli, ['compute', 'sys-perf', '--progressbar'])
            self.assertEqual(result.exit_code, 0)
            _, kwargs = mock_process_jobs.call_args
            self.assertTrue(kwargs['progressbar'])

        with patch(ns('jobs.process_jobs')) as mock_process_jobs:
            mock_process_jobs.return_value.__enter__.return_value = ()

            result = self.runner.invoke(cli, ['compute', 'sys-perf', '--no-progressbar'])
            self.assertEqual(result.exit_code, 0)
            _, kwargs = mock_process_jobs.call_args
            self.assertFalse(kwargs['progressbar'])

    @patch('signal_processing.commands.helpers.CommandConfiguration', autospec=True)
    def test_compute_creates_jobs(self, mock_command_config_cls):
        """ Test compute creates jobs. """

        mock_points = MagicMock(name='config')
        mock_points.aggregate.return_value = ()
        expected_config = MagicMock(
            name='config', points=mock_points, debug=0, log_file='/tmp/log_file')
        mock_command_config_cls.return_value = expected_config

        with patch(ns('helpers.generate_tests')) as mock_generate_tests, \
             patch(ns('helpers.generate_thread_levels')) as mock_generate_thread_levels, \
             patch(ns('jobs.process_jobs')) as mock_process_jobs, \
             patch(ns('jobs.Job')) as mock_job_cls:

            mock_process_jobs.return_value.__enter__.return_value = ()

            mock_generate_tests.return_value = [{'test': str(i)} for i in range(1)]
            test_identifiers = [{'test': str(i)} for i in range(5)]
            mock_generate_thread_levels.return_value = test_identifiers

            result = self.runner.invoke(cli, ['compute', 'sys-perf'])
            self.assertEqual(result.exit_code, 0)
            mock_job_cls.assert_has_calls([
                mock.call(
                    signal_processing.change_points.compute.compute_change_points,
                    arguments=(test_identifier, .001, expected_config),
                    kwargs=dict(min_points=500),
                    identifier=test_identifier) for test_identifier in test_identifiers
            ])

    @patch('signal_processing.commands.helpers.CommandConfiguration', autospec=True)
    def test_compute_jobs(self, mock_command_config_cls):
        """ Test compute job iteration. """

        mock_points = MagicMock(name='config')
        mock_points.aggregate.return_value = ()
        expected_config = MagicMock(
            name='config', points=mock_points, debug=0, log_file='/tmp/log_file')
        mock_command_config_cls.return_value = expected_config

        with patch(ns('jobs.process_jobs')) as mock_process_jobs:
            mock_job = MagicMock(name='job', exception=None, identifier={'test': 'name'})
            mock_process_jobs.return_value.__enter__.return_value = [mock_job]
            result = self.runner.invoke(cli, ['compute', 'sys-perf'])
            self.assertEqual(result.exit_code, 0)

    @patch('signal_processing.commands.helpers.CommandConfiguration', autospec=True)
    def test_compute_exceptions(self, mock_command_config_cls):
        """ Test compute exceptions. """

        mock_points = MagicMock(name='config')
        mock_points.aggregate.return_value = ()
        expected_config = MagicMock(
            name='config', points=mock_points, debug=0, log_file='/tmp/log_file')
        mock_command_config_cls.return_value = expected_config

        with patch(ns('jobs.process_jobs')) as mock_process_jobs:
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
