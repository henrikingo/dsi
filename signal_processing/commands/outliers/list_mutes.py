# -*- coding: utf-8 -*-
"""
Command to list outliers.
"""

import click

from signal_processing.outliers import list_mutes
from signal_processing.commands import helpers


@click.command(name='list-mutes')
@click.pass_obj
@click.option(
    '--human-readable/--no-human-readable',
    'human_readable',
    is_flag=True,
    default=True,
    help='Print output in a more human-friendly output.')
@click.option(
    '--limit',
    callback=helpers.validate_int_none_options,
    default='None',
    help='The maximum number of grouped failures to display.')
@click.option(
    '--no-older-than',
    callback=helpers.validate_int_none_options,
    default='none',
    help='''Don't consider grouped failures older than this number of days.
A perf BB rotation is 2 weeks, so 14 days seems appropriate''')
@click.option('--revision', 'revision', default=None, help='Specify a revision, defaults to None.')
@click.argument('project', required=True)
@click.argument('variant', required=False)
@click.argument('task', required=False)
@click.argument('test', required=False)
@click.argument('thread_level', required=False)
def list_mutes_command(command_config, human_readable, limit, no_older_than, revision, project,
                       variant, task, test, thread_level):
    # pylint: disable=too-many-arguments
    """
    Print list of mutes.

Arguments can be string or patterns, A pattern starts with /.

\b
PROJECT, the project name or a regex (like /^sys-perf-3.*/ or /^(sys-perf|performance)$/).
\b
Examples:
\b
    # List test failures for the sys-perf project
    $> outliers list
    $> outliers list sys-perf
\b
    # List the most recent failures for the sys-perf project
    $> outliers list sys-perf --limit 1
\b
    # List the failures since the start of day
    $> outliers list sys-perf --no-older-than 1
"""

    query = helpers.process_params(
        project, variant, task, test, revision=revision, thread_level=thread_level)
    list_mutes.list_mutes(query, human_readable, limit, no_older_than, command_config)
