"""
Unit tests for signal_processing/change_points.py.
"""
from __future__ import print_function
import unittest

# pylint: disable=invalid-name
from click.testing import CliRunner

from signal_processing.outliers_cli import cli


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

    def test_help_h_option(self):
        """ Test help with the `-h` option. """
        result = self.runner.invoke(cli, ['-h'])
        self.assertEqual(result.exit_code, 0)
        self.assertTrue(result.output.startswith("Usage"))

    def test_help_command(self):
        """ Test help command. """
        result = self.runner.invoke(cli, ['help'])
        self.assertEqual(result.exit_code, 0)
        self.assertTrue(result.output.startswith("Usage"))
