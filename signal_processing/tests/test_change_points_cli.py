"""
Unit tests for signal_processing/change_points_cli.py.

The tests for the individual commands can be found in signal_processing/commands/change_points/.
"""
import unittest

# pylint: disable=invalid-name
from click.testing import CliRunner

from signal_processing.change_points_cli import cli


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
