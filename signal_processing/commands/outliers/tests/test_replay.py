"""
Unit tests for signal_processing/commands/outliers/replay.py.
"""
# pylint: disable=missing-docstring
from __future__ import print_function
import unittest

from mock import MagicMock, patch, call

from click.testing import CliRunner

from signal_processing.commands.outliers.replay import _create_jobs
from signal_processing.outliers.detection import STANDARD_Z_SCORE
from signal_processing.outliers_cli import cli

NS = 'signal_processing.commands.outliers.replay'


def ns(relative_name):  # pylint: disable=invalid-name
    """Return a full name from a name relative to the tested module's name space."""
    return NS + '.' + relative_name


class ClickTest(unittest.TestCase):
    """
    Test Cli group command.
    """

    def setUp(self):
        self.runner = CliRunner()


class TestReplayParams(ClickTest):
    """
    Test config command.
    """

    def test_requires_params(self):
        """ Test replay with no parameters. """

        result = self.runner.invoke(cli, ['replay'])
        self.assertEqual(result.exit_code, 2)

    def test_help_h_option(self):
        """ Test help with the `-h` option. """
        result = self.runner.invoke(cli, ['replay', '-h'])
        self.assertEqual(result.exit_code, 0)
        self.assertTrue(result.output.startswith("Usage"))

    @patch(ns('jobs.process_jobs'), autospec=True)
    @patch('signal_processing.commands.helpers.CommandConfiguration', autospec=True)
    def test_basic(self, mock_command_config_cls, mock_process_jobs):
        """ Test outliers config. """
        mock_points = MagicMock(name='config')
        mock_points.aggregate.return_value = ()
        expected_config = MagicMock(
            name='config', points=mock_points, debug=0, log_file='/tmp/log_file')
        mock_command_config_cls.return_value = expected_config
        mock_process_jobs.return_value.__enter__.return_value = ()

        result = self.runner.invoke(cli, ['replay', 'sys-perf'])
        self.assertEqual(result.exit_code, 0)

    @patch(ns('helpers.process_params'), autospec=True)
    @patch('signal_processing.commands.helpers.CommandConfiguration', autospec=True)
    def test_no_jobs(self, mock_config, mock_process_params):
        """ Test outliers config correctly uses parameters. """
        expected_query = {'find': 'me'}
        mock_process_params.return_value = expected_query
        expected_config = MagicMock(name='config', debug=0, log_file='/tmp/log_file')
        mock_config.return_value = expected_config

        result = self.runner.invoke(
            cli,
            ['replay', 'sys-perf', 'linux-standalone', 'industry_benchmarks', 'ycsb_load', '1'])
        self.assertEqual(result.exit_code, 0)
        mock_process_params.assert_called_once_with(
            'sys-perf', 'linux-standalone', 'industry_benchmarks', 'ycsb_load', thread_level='1')

    @patch(ns('helpers.process_params'), autospec=True)
    @patch('signal_processing.commands.helpers.CommandConfiguration', autospec=True)
    def test_invalid_max_outliers(self, mock_config, mock_process_params):
        """ Test invalid max outliers fails. """
        expected_query = {'find': 'me'}
        mock_process_params.return_value = expected_query
        expected_config = MagicMock(name='config', debug=0, log_file='/tmp/log_file')
        mock_config.return_value = expected_config

        result = self.runner.invoke(cli, [
            'replay', 'sys-perf', 'linux-standalone', 'industry_benchmarks', 'ycsb_load', '1', '-m',
            '1.1'
        ])
        self.assertEqual(result.exit_code, 2)
        self.assertIn('are not valid outlier percentages', result.output)

    @patch(ns('helpers.process_params'), autospec=True)
    @patch('signal_processing.commands.helpers.CommandConfiguration', autospec=True)
    def test_invalid_negative_max_outliers(self, mock_config, mock_process_params):
        """ Test invalid max outliers fails. """
        expected_query = {'find': 'me'}
        mock_process_params.return_value = expected_query
        expected_config = MagicMock(name='config', debug=0, log_file='/tmp/log_file')
        mock_config.return_value = expected_config

        result = self.runner.invoke(cli, [
            'replay', 'sys-perf', 'linux-standalone', 'industry_benchmarks', 'ycsb_load', '1', '-m',
            '-1.1'
        ])
        self.assertEqual(result.exit_code, 2)
        self.assertIn('are not valid outlier percentages', result.output)

    @patch(ns('helpers.process_params'), autospec=True)
    @patch('signal_processing.commands.helpers.CommandConfiguration', autospec=True)
    def test_valid_max_outliers(self, mock_config, mock_process_params):
        """ Test invalid max outliers fails. """
        expected_query = {'find': 'me'}
        mock_process_params.return_value = expected_query
        expected_config = MagicMock(name='config', debug=0, log_file='/tmp/log_file')
        mock_config.return_value = expected_config

        result = self.runner.invoke(cli, [
            'replay', 'sys-perf', 'linux-standalone', 'industry_benchmarks', 'ycsb_load', '1', '-m',
            '0'
        ])
        self.assertEqual(result.exit_code, 0)


# pylint: disable=invalid-name
class TestCreateJobs(unittest.TestCase):
    """
    Test _create_jobs.
    """

    def test_no_identifiers(self):
        """ Test no identifiers generates no jobs. """
        test_identifiers = []
        mock_command_config = MagicMock(name='command_config')
        change_point_indexes = [-1]
        significance_levels = 0.05
        max_outliers = 0
        z_scores = [STANDARD_Z_SCORE]
        with patch(ns('generate_change_point_ranges')) as mock_generate_change_point_ranges,\
             patch(ns('PointsModel'), autospec=True):
            jobs = _create_jobs(mock_command_config, test_identifiers, change_point_indexes,
                                significance_levels, max_outliers, z_scores)
            self.assertEquals(jobs, [])
            mock_generate_change_point_ranges.assert_not_called()

    def test_one_identifier(self):
        """ Test no identifiers generates no jobs. """
        test_identifiers = [dict(project='project', variant='variant', task='task', test='test')]
        mock_command_config = MagicMock(name='command_config')
        change_point_indexes = [-1]
        significance_levels = [0.05]
        max_outliers = [0]
        z_scores = [STANDARD_Z_SCORE]
        with patch(ns('generate_change_point_ranges')) as mock_generate_change_point_ranges,\
             patch(ns('PointsModel'), autospec=True) as mock_clazz:
            mock_model = mock_clazz.return_value
            mock_generate_change_point_ranges.return_value = [(0, 1)]
            jobs = _create_jobs(mock_command_config, test_identifiers, change_point_indexes,
                                significance_levels, max_outliers, z_scores)
            self.assertEquals(len(jobs), 1)
            mock_generate_change_point_ranges.assert_called_once_with(
                test_identifiers[0], mock_model, change_point_indexes)

    def test_two_identifier(self):
        """ Test no identifiers generates no jobs. """
        test_identifiers = [
            dict(project='project', variant='variant', task='task', test='test'),
            dict(project='project', variant='variant', task='task', test='test')
        ]
        mock_command_config = MagicMock(name='command_config')
        change_point_indexes = [-1]
        significance_levels = [0.05]
        max_outliers = [0]
        z_scores = [STANDARD_Z_SCORE]
        with patch(ns('generate_change_point_ranges')) as mock_generate_change_point_ranges,\
             patch(ns('PointsModel'), autospec=True) as mock_clazz:
            mock_model = mock_clazz.return_value
            mock_generate_change_point_ranges.return_value = [(0, 1)]
            jobs = _create_jobs(mock_command_config, test_identifiers, change_point_indexes,
                                significance_levels, max_outliers, z_scores)
            self.assertEquals(len(jobs), 2)
            calls = [
                call(test_identifier, mock_model, change_point_indexes)
                for test_identifier in test_identifiers
            ]
            mock_generate_change_point_ranges.assert_has_calls(calls)

    def test_all_change_points(self):
        """ Test all change points overrides indexes. """
        test_identifiers = [dict(project='project', variant='variant', task='task', test='test')]
        mock_command_config = MagicMock(name='command_config')
        change_point_indexes = [-1]
        significance_levels = [0.05]
        max_outliers = [0]
        z_scores = [STANDARD_Z_SCORE]
        with patch(ns('generate_change_point_ranges')) as mock_generate_change_point_ranges,\
             patch(ns('PointsModel'), autospec=True) as mock_clazz:
            mock_model = mock_clazz.return_value
            mock_generate_change_point_ranges.return_value = [(0, 1)]
            jobs = _create_jobs(
                mock_command_config,
                test_identifiers,
                change_point_indexes,
                significance_levels,
                max_outliers,
                z_scores,
                all_change_points=True)
            self.assertEquals(len(jobs), 1)
            mock_generate_change_point_ranges.assert_called_once_with(test_identifiers[0],
                                                                      mock_model, [])

    # pylint: disable=too-many-locals
    def test_permutations(self):
        """ Test all change points overrides indexes. """
        test_identifiers = [dict(project='project', variant='variant', task='task', test='test')]
        mock_command_config = MagicMock(name='command_config')
        change_point_indexes = [-1]

        change_point_ranges = [(0, 1), (2, 3)]
        z_scores = range(3)
        max_outliers = range(4)
        significance_levels = range(5)

        with patch(ns('generate_change_point_ranges')) as mock_generate_change_point_ranges,\
             patch(ns('PointsModel'), autospec=True) as mock_clazz:
            mock_model = mock_clazz.return_value
            mock_generate_change_point_ranges.return_value = change_point_ranges
            jobs = _create_jobs(
                mock_command_config,
                test_identifiers,
                change_point_indexes,
                significance_levels,
                max_outliers,
                z_scores,
                all_change_points=True)
            number_of_change_points = 2
            number_of_z_scores = 3
            number_of_outliers = 4
            number_of_significance_levels = 5
            expected_number_of_jobs = number_of_change_points * number_of_z_scores * \
                number_of_outliers * number_of_significance_levels
            self.assertEquals(len(jobs), expected_number_of_jobs)
            mock_generate_change_point_ranges.assert_called_once_with(test_identifiers[0],
                                                                      mock_model, [])
