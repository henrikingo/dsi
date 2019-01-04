# -*- coding: utf-8 -*-
"""
Command to list change points.
"""
import os

import click
import yaml

from analysis.evergreen import evergreen_client
from signal_processing.change_points import list_failures
from signal_processing.commands import helpers


@click.command(name='failures')
@click.pass_obj
@click.option(
    '--human-readable/--no-human-readable',
    'human_readable',
    is_flag=True,
    default=True,
    help='Print output in a more human-friendly output.')
@click.option(
    '--evergreen-config',
    'evergreen_config',
    default='~/.evergreen.yml',
    help='The location of the evergreen config file.')
@click.option(
    '--limit',
    callback=helpers.validate_int_none_options,
    default='None',
    help='The maximum number of grouped failures to display.')
@click.option(
    '--no-older-than',
    callback=helpers.validate_int_none_options,
    default='14',
    help='''Don't consider grouped failures older than this number of days.
A perf BB rotation is 2 weeks, so 14 days seems appropriate''')
@click.option(
    '--show-wtdevelop/--hide-wtdevelop',
    'show_wtdevelop',
    is_flag=True,
    default=False,
    help='Filter or show wtdevelop tasks (defaults to hidden). The filtering happens in the client.'
)
@click.option(
    '--show-patches/--hide-patches',
    'show_patches',
    is_flag=True,
    default=False,
    help='Filter or show wtdevelop tasks (defaults to hidden). The filtering happens in the client.'
)
@click.argument('project', required=True)
def list_failures_command(command_config, human_readable, evergreen_config, limit, no_older_than,
                          show_wtdevelop, show_patches, project):
    # pylint: disable=too-many-arguments
    """
    Print list of failures.

Arguments can be string or patterns, A pattern starts with /.

\b
PROJECT, the project name or a regex (like /^sys-perf-3.*/ or /^(sys-perf|performance)$/).
\b
Examples:
\b
    # List test failures for the sys-perf project
    $> change-points failures
    $> change-points failures sys-perf
\b
    # List the most recent failures for the sys-perf project
    $> change-points failures sys-perf --limit 1
\b
    # List the failures since the start of day
    $> change-points failures sys-perf --no-older-than 1
"""

    path = os.path.expanduser(evergreen_config)
    with open(path) as config_file:
        evg_client = evergreen_client.Client(yaml.load(config_file))

    list_failures.list_failures(project, show_wtdevelop, show_patches, human_readable, limit,
                                no_older_than, evg_client, command_config)
