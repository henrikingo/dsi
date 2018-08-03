"""
Unit tests for signal_processing/detect_changes.py.
"""
import unittest

from mock import patch

# pylint: disable=invalid-name
from signal_processing.change_points import cli
from click.testing import CliRunner


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
        """ Test group."""
        result = self.runner.invoke(cli)
        self.assertEqual(result.exit_code, 0)


class TestHelp(ClickTest):
    """
    Test help command.
    """

    def test_help(self):
        """ Test help. """
        result = self.runner.invoke(cli, ['help'])
        self.assertEqual(result.exit_code, 0)


class TestMark(ClickTest):
    """
    Test mark command.
    """

    def test_mark_requires_some_params(self):
        """ Test mark requires params. """
        result = self.runner.invoke(cli, ['mark'])
        self.assertEqual(result.exit_code, 2)

    @patch('signal_processing.change_points.mark.mark_change_points', autospec=True)
    @patch('signal_processing.change_points.helpers.CommandConfiguration', autospec=True)
    def test_mark(self, mock_config, mock_mark):  # pylint: disable=unused-argument
        """ Test mark. """
        result = self.runner.invoke(cli, ['-n', 'mark', 'badf', 'sys-perf'], obj=mock_config)
        self.assertEqual(result.exit_code, 0)


class TestHide(ClickTest):
    """
    Test hide command.
    """

    def test_hide_requires_some_params(self):
        """ Test hide requires params. """
        result = self.runner.invoke(cli, ['hide'])
        self.assertEqual(result.exit_code, 2)

    @patch('signal_processing.change_points.mark.mark_change_points', autospec=True)
    @patch('signal_processing.change_points.helpers.CommandConfiguration', autospec=True)
    def test_hide(self, mock_config, mock_mark):  # pylint: disable=unused-argument
        """ Test hide."""
        result = self.runner.invoke(cli, ['-n', 'hide', 'badf', 'sys-perf'], obj=mock_config)
        self.assertEqual(result.exit_code, 0)


class TestUpdate(ClickTest):
    """
    Test update command.
    """

    def test_update_requires_some_params(self):
        """ Test update requires some params. """
        result = self.runner.invoke(cli, ['update'])
        self.assertEqual(result.exit_code, 2)

    @patch('signal_processing.change_points.update.update_change_points', autospec=True)
    @patch('signal_processing.change_points.helpers.CommandConfiguration', autospec=True)
    def test_update(self, mock_config, mock_update):  # pylint: disable=unused-argument
        """ Test update. """
        result = self.runner.invoke(cli, ['-n', 'update', 'badf', 'sys-perf'], obj=mock_config)
        self.assertEqual(result.exit_code, 0)


class TestList(ClickTest):
    """
    Test list command.
    """

    @patch('signal_processing.change_points.list_change_points', autospec=True)
    @patch('signal_processing.change_points.helpers.CommandConfiguration', autospec=True)
    def test_list_no_params(self, mock_config, mock_list):  # pylint: disable=unused-argument
        """ Test list with no params. """
        result = self.runner.invoke(cli, ['list'])
        self.assertEqual(result.exit_code, 0)


class TestCompare(ClickTest):
    """
    Test compare command.
    """

    @patch('signal_processing.change_points.compare', autospec=True)
    @patch('signal_processing.change_points.helpers.CommandConfiguration', style=['bmh'])
    def test_list_no_params(self, mock_config, mock_compare):  # pylint: disable=unused-argument
        """ Test list no params. """

        self.runner.invoke(cli, ['compare'])


class TestCompute(ClickTest):
    """
    Test compute command.
    """

    @patch('signal_processing.change_points.compute.compute_change_points', autospec=True)
    @patch('signal_processing.change_points.helpers.CommandConfiguration', style=['bmh'])
    def test_compute_requires_params(self, mock_config, mock_compare):
        # pylint: disable=unused-argument
        """ Test compute with no params. """

        result = self.runner.invoke(cli, ['compute'])
        self.assertEqual(result.exit_code, 2)

    @patch('signal_processing.change_points.compute.compute_change_points', autospec=True)
    @patch('signal_processing.change_points.helpers.CommandConfiguration', style=['bmh'])
    def test_compute(self, mock_config, mock_compare):  # pylint: disable=unused-argument
        """ Test compute. """

        result = self.runner.invoke(cli, ['compute', 'sys-perf'])
        self.assertEqual(result.exit_code, 0)


class TestVisualize(ClickTest):
    """
    Test visualize command.
    """

    @unittest.skip("test_visualize_no_params fails in evergreen")
    @patch('signal_processing.change_points.visualize', autospec=True)
    @patch('signal_processing.change_points.helpers.CommandConfiguration', style=['bmh'])
    def test_visualize_no_params(self, mock_config, mock_visualize):
        # pylint: disable=unused-argument
        """ Test visualize with no params. """

        result = self.runner.invoke(cli, ['visualize'])
        self.assertEqual(result.exit_code, 0)
