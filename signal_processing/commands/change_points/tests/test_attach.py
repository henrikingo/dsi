"""
Unit tests for signal_processing/commands/change_points/attach.py.
"""
import unittest

import click.testing
from mock import ANY, MagicMock, patch

from signal_processing.change_points_cli import cli

NS = 'signal_processing.commands.change_points.attach'


def ns(relative_name):  # pylint: disable=invalid-name
    """Return a full name from a name relative to the tested module's name space."""
    return NS + '.' + relative_name


class TestAttach(unittest.TestCase):
    """
    Test attach command.
    """

    def setUp(self):
        self.runner = click.testing.CliRunner()

    def _test_params_fails(self, args=None, name='build_failure'):
        """ Test with invalid params. """
        if args is None:
            args = []
        result = self.runner.invoke(cli, ['attach'] + args)
        self.assertEqual(result.exit_code, 2)
        self.assertIn('Error: Missing argument \"{}\"'.format(name), result.output)

    def test_no_params_fails(self):
        """ Test attach no params. """
        self._test_params_fails()

    def test_no_revision_fails(self):
        """ Test attach no revision. """
        self._test_params_fails(args=['badf'], name='revision')

    def test_no_project_fails(self):
        """ Test attach no project. """
        self._test_params_fails(args=['badf', 'revision'], name='project')

    def test_no_variant_fails(self):
        """ Test attach no project. """
        self._test_params_fails(args=['badf', 'revision', 'project'], name='variant')

    def test_no_task_fails(self):
        """ Test attach no project. """
        self._test_params_fails(args=['badf', 'revision', 'project', 'variant'], name='task')

    def test_no_test_fails(self):
        """ Test attach no project. """
        self._test_params_fails(
            args=['badf', 'revision', 'project', 'variant', 'task'], name='test')

    def _test(self, keyring_flag=None, use_keyring=True, fix_flag=None, fix=False):
        """ Test attach. """

        # pylint: disable=too-many-locals
        with patch(ns('attach.attach'), autospec=True) as mock_attach, \
            patch('signal_processing.commands.helpers.CommandConfiguration', autospec=True) as mock_config, \
            patch(ns('jira_keyring'), autospec=True) as mock_keyring, \
            patch(ns('helpers.process_params_for_points'), autospec=True) as mock_process_params_for_points, \
            patch(ns('helpers.get_matching_tasks')) as mock_get_matching_tasks:

            expected_config = MagicMock(name='config', debug=0, log_file='/tmp/log_file')
            mock_config.return_value = expected_config

            mock_issue = MagicMock(name='issue')
            mock_jira = MagicMock(name='jira')
            mock_jira.issue.return_value = mock_issue

            mock_keyring.return_value.__enter__.return_value = mock_jira

            mock_process_params_for_points.return_value = 'query'
            mock_get_matching_tasks.return_value = []
            build_failure = 'BF-11372'
            revision = 'badf'
            project = 'sys-perf'
            variant = 'linux-3-shard'
            task = 'crud_workloads'
            test = 'fio_streaming_bandwidth_test_write_iops'

            args = [
                'attach', build_failure, revision, project, variant, task, test, keyring_flag,
                fix_flag
            ]

            result = self.runner.invoke(cli, [arg for arg in args if arg is not None])
            self.assertEqual(result.exit_code, 0)

            mock_process_params_for_points.assert_called_once_with(
                project, variant, task, test, revision=revision)
            mock_get_matching_tasks.assert_called_once_with(expected_config.points, 'query')
            mock_attach.assert_called_once_with(ANY, [], fix, expected_config)
            mock_jira.issue.assert_called_once_with(build_failure)
            mock_keyring.assert_called_once_with(None, None, use_keyring=use_keyring)

    def test(self):
        """ Test attach default (keyring / fail). """
        self._test()

    def test_fail(self):
        """ Test attach fail. """
        self._test(fix_flag='--fail')

    def test_fix(self):
        """ Test attach fix. """
        self._test(fix_flag='--fix', fix=True)

    def test_keyring(self):
        """ Test attach --keyring. """
        self._test(keyring_flag='--keyring')

    def test_no_keyring(self):
        """ Test attach --no-keyring. """
        self._test(keyring_flag='--no-keyring', use_keyring=False)

    def test_guest(self):
        """ Test attach guest (no keyring). """
        self._test(keyring_flag='--guest', use_keyring=False)

    def test_keyring_and_fail(self):
        """ Test attach --keyring / --fail. """
        self._test(keyring_flag='--keyring', fix_flag='--fail')


class TestDetach(unittest.TestCase):
    """
    Test detach command.
    """

    def setUp(self):
        self.runner = click.testing.CliRunner()

    def _test_params_fails(self, args=None, name='build_failure'):
        """ Test with invalid params. """
        if args is None:
            args = []
        result = self.runner.invoke(cli, ['detach'] + args)
        self.assertEqual(result.exit_code, 2)
        self.assertIn('Error: Missing argument \"{}\"'.format(name), result.output)

    def test_no_params_fails(self):
        """ Test detach no params. """
        self._test_params_fails()

    def test_no_revision_fails(self):
        """ Test detach no params. """
        self._test_params_fails(args=['badf'], name='revision')

    def test_no_project_fails(self):
        """ Test detach no params. """
        self._test_params_fails(args=['badf', 'revision'], name='project')

    def _test(self, keyring_flag=None, use_keyring=True, fix_flag=None, fix=False):

        # pylint: disable=too-many-locals
        with patch(ns('attach.detach'), autospec=True) as mock_detach, \
             patch('signal_processing.commands.helpers.CommandConfiguration', autospec=True) as mock_config, \
             patch(ns('jira_keyring'), autospec=True) as mock_keyring, \
             patch(ns('helpers.process_params_for_points')) as mock_process_params, \
             patch(ns('helpers.get_matching_tasks'), autospec=True) as mock_get_matching_tasks:

            expected_config = MagicMock(name='config', debug=0, log_file='/tmp/log_file')
            mock_config.return_value = expected_config

            mock_issue = MagicMock(name='issue')
            mock_jira = MagicMock(name='jira')
            mock_jira.issue.return_value = mock_issue

            mock_keyring.return_value.__enter__.return_value = mock_jira
            query = 'query'
            mock_process_params.return_value = query
            mock_get_matching_tasks.return_value = []
            build_failure = 'BF-11372'
            revision = 'badf'
            project = 'sys-perf'

            args = ['detach', build_failure, revision, project, keyring_flag, fix_flag]

            result = self.runner.invoke(cli, [arg for arg in args if arg is not None])
            self.assertEqual(result.exit_code, 0)

            mock_process_params.assert_called_once_with(
                project, None, None, None, revision=revision)
            mock_get_matching_tasks.assert_called_once_with(expected_config.points, query)
            mock_detach.assert_called_once_with(ANY, [], fix, expected_config)
            mock_keyring.assert_called_once_with(None, None, use_keyring=use_keyring)
            mock_jira.issue.assert_called_once_with(build_failure)

    def test(self):
        """ Test detach default (keyring / fail). """
        self._test()

    def test_fail(self):
        """ Test detach fail. """
        self._test(fix_flag='--fail')

    def test_fix(self):
        """ Test detach fix. """
        self._test(fix_flag='--fix', fix=True)

    def test_keyring(self):
        """ Test detach --keyring. """
        self._test(keyring_flag='--keyring')

    def test_no_keyring(self):
        """ Test detach --no-keyring. """
        self._test(keyring_flag='--no-keyring', use_keyring=False)

    def test_guest(self):
        """ Test detach --guest (no keyring). """
        self._test(keyring_flag='--guest', use_keyring=False)

    def test_keyring_and_fail(self):
        """ Test detach --keyring / --fail. """
        self._test(keyring_flag='--keyring', fix_flag='--fail')
