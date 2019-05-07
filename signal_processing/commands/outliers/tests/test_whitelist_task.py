"""
Unit tests for signal_processing/commands/outliers/whitelist_task.py.
"""
from __future__ import print_function

import unittest

from click.testing import CliRunner
from mock import MagicMock, patch

from signal_processing.outliers_cli import cli

NS = 'signal_processing.commands.outliers.whitelist_task'


def ns(relative_name):  # pylint: disable=invalid-name
    """Return a full name from a name relative to the tested module's name space."""
    return NS + '.' + relative_name


def flatten(args):
    """ flatten a list of lists into a single level list. """
    return [item for sublist in args for item in sublist]


class ClickTest(unittest.TestCase):
    """
    Test Cli group command.
    """

    def setUp(self):
        self.runner = CliRunner()

    def _invoke(self, *args, **kwargs):
        """ invoke the cli command. """
        # pylint: disable=no-member
        combined = filter(None, list(args) + flatten([[k, v] for k, v in kwargs.iteritems()]))

        command = ['whitelist', self.COMMAND_NAME]
        command.extend(combined)
        return self.runner.invoke(cli, command)


class TestList(ClickTest):
    """
    Test outliers whitelist list.
    """
    COMMAND_NAME = 'list'

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

    def _test_invoke(self, expected, project, variant, task, options=None):
        """ whitelist list helper. """

        options = {} if options is None else options
        with patch(ns('whitelist_task.list_whitelist'), autospec=True) as list_task_mock, \
             patch('signal_processing.commands.helpers.CommandConfiguration', autospec=True) as command_config_cls_mock:

            expected_config = MagicMock(name='config', debug=0, log_file='/tmp/log_file')
            command_config_cls_mock.return_value = expected_config

            args = [project, variant, task]
            result = self._invoke(*args, **options)
            self.assertEqual(result.exit_code, 0)

            limit = options.get('--limit', 10)
            no_older_than = options.get('--no-older-than', 14)

            human_readable = '--no-human-readable' not in options
            show_wtdevelop = '--show-wtdevelop' in options and '--hide-wtdevelop' not in options

            list_task_mock.assert_called_once_with(expected, limit, no_older_than, human_readable,
                                                   show_wtdevelop, expected_config)

    def test_basic(self):
        """ Test whitelist list with defaults. """
        project = 'sys-perf'
        variant = None
        task = None
        self._test_invoke({'project': project}, project, variant, task)

    def test_full(self):
        """ Test whitelist list with values. """
        project = 'sys-perf'
        variant = 'linux-standalone'
        task = 'bestbuy-agg'
        options = {
            '--limit': 20,
            '--no-older-than': 28,
            '--human-readable': None,
            '--show-wtdevelop': None
        }
        self._test_invoke({
            'project': project,
            'variant': variant,
            'task': task
        }, project, variant, task, options)

    def test_inverted(self):
        """ Test whitelist list with no and hide options. """
        project = 'sys-perf'
        variant = 'linux-standalone'
        task = 'bestbuy-agg'
        options = {'--no-human-readable': None, '--hide-wtdevelop': None}
        self._test_invoke({
            'project': project,
            'variant': variant,
            'task': task
        }, project, variant, task, options)


class TestAdd(ClickTest):
    """
    Test outliers whitelist add command.
    """

    COMMAND_NAME = 'add'

    def test_requires_params(self):
        """ Test whitelist add with no parameters. """

        result = self._invoke()
        self.assertEqual(result.exit_code, 2)
        self.assertIn("Missing argument", result.output)

        result = self._invoke('revision')
        self.assertEqual(result.exit_code, 2)
        self.assertIn("Missing argument", result.output)

    def test_help_h_option(self):
        """ Test help with the `-h` option. """
        result = self._invoke('-h')
        self.assertEqual(result.exit_code, 0)
        self.assertTrue(result.output.startswith("Usage"))

    def _test_invoke(self, expected, *args):
        """ whitelist add helper. """

        with patch(ns('whitelist_task.add_whitelist'), autospec=True) as mock_view_configuration, \
                patch('signal_processing.commands.helpers.CommandConfiguration', autospec=True) as mock_command_config_cls:

            expected_config = MagicMock(name='config', debug=0, log_file='/tmp/log_file')
            mock_command_config_cls.return_value = expected_config

            result = self._invoke(*args)
            self.assertEqual(result.exit_code, 0)
            mock_view_configuration.assert_called_once_with(expected, expected_config)

    def test_basic(self):
        """ Test whitelist add. """
        project = 'sys-perf'
        revision = 'revision'
        self._test_invoke({'project': project, 'revision': revision}, revision, project)

    def test_full(self):
        """ Test whitelist add. """
        revision = 'revision'
        project = 'sys-perf'
        variant = 'linux-standalone'
        task = 'bestbuy-agg'
        self._test_invoke({
            'revision': revision,
            'project': project,
            'variant': variant,
            'task': task,
        }, revision, project, variant, task)


class TestRemove(ClickTest):
    """
    Test outliers whitelist remove command.
    """

    COMMAND_NAME = 'remove'

    def test_requires_params(self):
        """ Test whitelist remove with no parameters. """

        result = self._invoke()
        self.assertEqual(result.exit_code, 2)
        self.assertIn("Missing argument", result.output)

        result = self._invoke('revision')
        self.assertEqual(result.exit_code, 2)
        self.assertIn("Missing argument", result.output)

        result = self._invoke('revision', 'project')
        self.assertEqual(result.exit_code, 2)
        self.assertIn("Missing argument", result.output)

        result = self._invoke('revision', 'project', 'variant')
        self.assertEqual(result.exit_code, 2)
        self.assertIn("Missing argument", result.output)

    def test_help_h_option(self):
        """ Test help with the `-h` option. """
        result = self._invoke('-h')
        self.assertEqual(result.exit_code, 0)
        self.assertTrue(result.output.startswith("Usage"))

    def _test_invoke(self, expected, *args):
        """ whitelist remove helper. """

        with patch(ns('whitelist_task.remove_whitelist'), autospec=True) as remove_mock,\
                patch('signal_processing.commands.helpers.CommandConfiguration', autospec=True) as command_config_cls_mock:

            expected_config = MagicMock(name='config', debug=0, log_file='/tmp/log_file')
            command_config_cls_mock.return_value = expected_config

            result = self._invoke(*args)
            self.assertEqual(result.exit_code, 0)
            remove_mock.assert_called_once_with(expected, expected_config)

    def test_full(self):
        """ Test whitelist remove. """
        revision = 'revision'
        project = 'sys-perf'
        variant = 'linux-standalone'
        task = 'bestbuy-agg'
        self._test_invoke({
            'revision': revision,
            'project': project,
            'variant': variant,
            'task': task,
        }, revision, project, variant, task)
