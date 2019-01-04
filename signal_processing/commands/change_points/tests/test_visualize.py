"""
Unit tests for signal_processing/commands/change_points/visualize.py.
"""
import unittest

import click.testing
from mock import patch

from signal_processing.change_points_cli import cli

NS = 'signal_processing.commands.change_points.visualize'


def ns(relative_name):  # pylint: disable=invalid-name
    """Return a full name from a name relative to the tested module's name space."""
    return NS + '.' + relative_name


class TestVisualize(unittest.TestCase):
    """
    Test visualize command.
    """

    def setUp(self):
        self.runner = click.testing.CliRunner()

    # pylint: disable=unused-argument
    @unittest.skip("test_visualize_no_params fails in evergreen")
    @patch(ns('visualize'), autospec=True)
    @patch('signal_processing.commands.helpers.CommandConfiguration', style=['bmh'])
    def test_visualize_no_params(self, mock_config, mock_visualize):
        """ Test visualize with no parameters. """

        result = self.runner.invoke(cli, ['visualize'])
        self.assertEqual(result.exit_code, 0)
