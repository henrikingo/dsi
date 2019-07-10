# -*- coding: utf-8 -*-
"""
Command to list outliers.
"""

import click

from signal_processing.detect_outliers import DETECTED_HIGH_CONFIDENCE, DETECTED_LOW_CONFIDENCE
from signal_processing.outliers import list_outliers
from signal_processing.commands import helpers


@click.command(name='list')
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
    default='14',
    help='''Don't consider grouped failures older than this number of days.
A perf BB rotation is 2 weeks, so 14 days seems appropriate''')
@click.option(
    '--type',
    'types',
    multiple=True,
    default=[DETECTED_HIGH_CONFIDENCE],
    type=click.Choice([DETECTED_HIGH_CONFIDENCE, DETECTED_LOW_CONFIDENCE]))
@click.option('--marked/ --no-marked', 'marked', default=False, is_flag=True)
@click.option('--revision', 'revision', default=None, help='Specify a revision, defaults to None.')
@click.argument('project', required=True)
@click.argument('variant', required=False)
@click.argument('task', required=False)
@click.argument('test', required=False)
@click.argument('thread_level', required=False)
def list_outliers_command(command_config, human_readable, limit, no_older_than, types, marked,
                          revision, project, variant, task, test, thread_level):
    # pylint: disable=too-many-arguments
    """
    Print list of outliers.

Arguments can be string or patterns, A pattern starts with /.

\b
PROJECT, the project name or a regex (like /^sys-perf-3.*/ or /^(sys-perf|performance)$/).
\b
Examples:
\b
    # List outliers for the sys-perf project
    $> outliers list
    $> outliers list sys-perf
\b
    # List the most outliers for the sys-perf project
    $> outliers list sys-perf --limit 1
\b
    # List the outliers since the start of day
    $> outliers list sys-perf --no-older-than 1
"""

    query = helpers.process_params_for_points(
        project, variant, task, test, revision=revision, thread_level=thread_level)
    list_outliers.list_outliers(query, marked, types, human_readable, limit, no_older_than,
                                command_config)
