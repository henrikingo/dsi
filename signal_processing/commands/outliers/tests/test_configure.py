"""
Unit tests for signal_processing/commands/outliers/evaluate.py.
"""
from __future__ import print_function

import json
import unittest

from click.testing import CliRunner
from mock import MagicMock, patch

from signal_processing.outliers_cli import cli

NS = 'signal_processing.commands.outliers.configure'


def ns(relative_name):  # pylint: disable=invalid-name
    """Return a full name from a name relative to the tested module's name space."""
    return NS + '.' + relative_name


class ClickTest(unittest.TestCase):
    """
    Test Cli group command.
    """

    def setUp(self):
        self.runner = CliRunner()

    def _invoke(self, *args):
        """ invoke the cli command. """

        # pylint: disable=no-member
        command = ['configure', self.COMMAND_NAME]
        command.extend(list(args))
        return self.runner.invoke(cli, command)


class TestView(ClickTest):
    """
    Test outliers configure view command.
    """
    COMMAND_NAME = 'view'

    def test_requires_params(self):
        """ Test outliers with no parameters. """

        result = self._invoke()
        self.assertEqual(result.exit_code, 2)
        self.assertIn("Missing argument", result.output)

    def test_help_h_option(self):
        """ Test help with the `-h` option. """
        result = self._invoke('-h')
        self.assertEqual(result.exit_code, 0)
        self.assertTrue(result.output.startswith("Usage"))

    def _test_invoke(self, expected, *args):
        """ Test outliers config. """

        with patch(ns('configure.view_configuration'), autospec=True) as mock_view_configuration, \
             patch('signal_processing.commands.helpers.CommandConfiguration', autospec=True) as mock_command_config_cls:

            expected_config = MagicMock(name='config', debug=0, log_file='/tmp/log_file')
            mock_command_config_cls.return_value = expected_config

            result = self._invoke(*args)
            self.assertEqual(result.exit_code, 0)
            mock_view_configuration.assert_called_once_with(expected, expected_config)

    def test_basic(self):
        """ Test outliers config. """
        project = 'sys-perf'
        self._test_invoke({'project': project}, project)

    def test_full(self):
        """ Test outliers config. """
        project = 'sys-perf'
        variant = 'linux-standalone'
        task = 'bestbuy-agg'
        test = 'find-useAgg'
        thread_level = '1'
        self._test_invoke({
            'project': project,
            'variant': variant,
            'task': task,
            'test': test,
            'thread_level': thread_level
        }, project, variant, task, test, thread_level)


class TestSet(ClickTest):
    """
    Test outliers configure set command.
    """

    COMMAND_NAME = 'set'

    def test_requires_params(self):
        """ Test outliers with no parameters. """

        result = self._invoke()
        self.assertEqual(result.exit_code, 2)
        self.assertIn("Missing argument", result.output)

    def test_help_h_option(self):
        """ Test help with the `-h` option. """
        result = self._invoke('-h')
        self.assertEqual(result.exit_code, 0)
        self.assertTrue(result.output.startswith("Usage"))

    def _test_invoke(self, expected, *args, **kwargs):
        """ Test outliers config. """

        with patch(ns('configure.set_configuration'), autospec=True) as mock_view_configuration, \
             patch('signal_processing.commands.helpers.CommandConfiguration', autospec=True) as mock_command_config_cls:

            expected_config = MagicMock(name='config', debug=0, log_file='/tmp/log_file')
            mock_command_config_cls.return_value = expected_config

            args = list(args)
            args.extend(('--json', json.dumps(kwargs)))
            result = self._invoke(*args)
            self.assertEqual(result.exit_code, 0)
            mock_view_configuration.assert_called_once_with(expected, kwargs, expected_config)

    def test_basic(self):
        """ Test outliers config. """
        project = 'sys-perf'
        self._test_invoke({'project': project}, project, max_percent=0.15)

    def test_full(self):
        """ Test outliers config. """
        project = 'sys-perf'
        variant = 'linux-standalone'
        task = 'bestbuy-agg'
        test = 'find-useAgg'
        thread_level = '1'
        self._test_invoke(
            {
                'project': project,
                'variant': variant,
                'task': task,
                'test': test,
                'thread_level': thread_level
            },
            project,
            variant,
            task,
            test,
            thread_level,
            max_percent=0.15)


class TestUnset(ClickTest):
    """
    Test outliers configure set command.
    """

    COMMAND_NAME = 'unset'

    def test_requires_params(self):
        """ Test outliers with no parameters. """

        result = self._invoke()
        self.assertEqual(result.exit_code, 2)
        self.assertIn("Missing argument", result.output)

    def test_help_h_option(self):
        """ Test help with the `-h` option. """
        result = self._invoke('-h')
        self.assertEqual(result.exit_code, 0)
        self.assertTrue(result.output.startswith("Usage"))

    def _test_invoke(self, expected, *args, **kwargs):
        """ Test outliers config. """

        with patch(ns('configure.unset_configuration'), autospec=True) as mock_view_configuration, \
             patch('signal_processing.commands.helpers.CommandConfiguration', autospec=True) as mock_command_config_cls:

            expected_config = MagicMock(name='config', debug=0, log_file='/tmp/log_file')
            mock_command_config_cls.return_value = expected_config

            args = list(args)
            args.extend(('--json', json.dumps(kwargs)))
            result = self._invoke(*args)
            self.assertEqual(result.exit_code, 0)
            mock_view_configuration.assert_called_once_with(expected, kwargs, expected_config)

    def test_basic(self):
        """ Test outliers config. """
        project = 'sys-perf'
        self._test_invoke({'project': project}, project, max_percent=0.15)

    def test_full(self):
        """ Test outliers config. """
        project = 'sys-perf'
        variant = 'linux-standalone'
        task = 'bestbuy-agg'
        test = 'find-useAgg'
        thread_level = '1'
        self._test_invoke(
            {
                'project': project,
                'variant': variant,
                'task': task,
                'test': test,
                'thread_level': thread_level
            },
            project,
            variant,
            task,
            test,
            thread_level,
            max_percent=0.15)


class TestDelete(ClickTest):
    """
    Test outliers configure delete command.
    """

    COMMAND_NAME = 'delete'

    def test_requires_params(self):
        """ Test outliers with no parameters. """

        result = self._invoke()
        self.assertEqual(result.exit_code, 2)
        self.assertIn("Missing argument", result.output)

    def test_help_h_option(self):
        """ Test help with the `-h` option. """
        result = self._invoke('-h')
        self.assertEqual(result.exit_code, 0)
        self.assertTrue(result.output.startswith("Usage"))

    def _test_invoke(self, expected, *args):
        """ Test outliers config. """

        with patch(ns('configure.delete_configuration'), autospec=True) as mock_view_configuration, \
             patch('signal_processing.commands.helpers.CommandConfiguration', autospec=True) as mock_command_config_cls:

            expected_config = MagicMock(name='config', debug=0, log_file='/tmp/log_file')
            mock_command_config_cls.return_value = expected_config

            result = self._invoke(*args)
            self.assertEqual(result.exit_code, 0)
            mock_view_configuration.assert_called_once_with(expected, expected_config)

    def test_basic(self):
        """ Test outliers config. """
        project = 'sys-perf'
        self._test_invoke({'project': project}, project)

    def test_full(self):
        """ Test outliers config. """
        project = 'sys-perf'
        variant = 'linux-standalone'
        task = 'bestbuy-agg'
        test = 'find-useAgg'
        thread_level = '1'
        self._test_invoke({
            'project': project,
            'variant': variant,
            'task': task,
            'test': test,
            'thread_level': thread_level
        }, project, variant, task, test, thread_level)
