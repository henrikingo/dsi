#!/usr/bin/env python2.7
"""
Cli wrapper for various change point operations

To get access to the help try the following command:

    $> change-points help
"""
import logging
import os

import click

from bin.common import log
from signal_processing.commands import CommandConfiguration, list_change_points, \
    mark_change_points, update_change_points, process_excludes, process_params, PROCESSED_TYPES, \
    PROCESSED_TYPE_HIDDEN, PROCESSED_TYPE_ACKNOWLEDGED

DB = "perf"
PROCESSED_CHANGE_POINTS = 'processed_change_points'
CHANGE_POINTS = 'change_points'
POINTS = 'points'
BUILD_FAILURES = 'build_failures'

LOG = logging.getLogger(__name__)

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.group(context_settings=CONTEXT_SETTINGS, invoke_without_command=True)
@click.option('-d', '--debug', count=True,
              help='Enable debug output, you can pass multiple -ddddd etc.')
@click.option('-l', '--logfile', count=True,
              help='The log file to write to, defaults to None.')
@click.option('-o', '--out', default="/tmp", help="The location to save any files in.")
@click.option('-f', '--format', 'file_format', default="png",
              help='The format to save any files in.')
@click.option('-u', '--mongo-uri', default='mongodb://localhost:27017/' + DB,
              help='MongoDB connection string. The database name comes from here too.')
@click.option('-q', '--queryable', default=False, help="Print ids as queries")
@click.option('-n', '--dry_run', is_flag=True, default=False, help="Don't actually run anything.")
@click.option('-c',
              '--compact/--expanded',
              'compact',
              default=True,
              help='Display objects one / line.')
@click.option('--points', default=POINTS, help="The points collection name.")
@click.option('--change_points', default=CHANGE_POINTS, help='The change points collection name.')
@click.option('--processed_change_points', default=PROCESSED_CHANGE_POINTS,
              help='The processed change points collection name.')
@click.option('--build_failures', default=BUILD_FAILURES,
              help='The build failures collection name.')
@click.pass_context
def cli(context, debug, logfile, out, file_format, mongo_uri, queryable, dry_run, compact,
        points, change_points, processed_change_points, build_failures):
    # pylint: disable=missing-docstring, too-many-arguments
    log.setup_logging(debug > 0, filename=os.path.expanduser(logfile) if logfile else logfile)
    context.obj = CommandConfiguration(debug, out, file_format, mongo_uri, queryable, dry_run,
                                       compact, points, change_points,
                                       processed_change_points, build_failures)
    if context.invoked_subcommand is None:
        print context.get_help()


@cli.command(name='help')
@click.pass_context
def help_command(context):
    """
    Show the help message and exit.
    """
    print context.parent.get_help()


@cli.command(name="mark")
@click.pass_obj
@click.option('--exclude', 'exclude_patterns', multiple=True,
              help='Exclude all points matching this pattern. This parameter can be provided ' +
              'multiple times.')
@click.argument('revision', required=True)
@click.argument('project', required=True)
@click.argument('variant', required=False)
@click.argument('task', required=False)
@click.argument('test', required=False)
@click.argument('thread_level', required=False)
def mark_command(command_config, exclude_patterns, revision, project, variant, task, test,
                 thread_level):
    # pylint: disable=too-many-arguments, too-many-function-args
    """
    Mark change point(s) as acknowledged.This process creates a copy of a change_points (ephemeral
output of the signal processing algorithm) in the (persistent) processed_change_point collection.

Arguments can be string or patterns, A pattern starts with /.

\b
REVISION, the revision of the change point. This parameter is mandatory.
PROJECT, the project name or a regex (like /^sys-perf-3.*/ or /^(sys-perf|performance)$/). This
parameter is mandatory.
VARIANT, the build variant or a regex.
TASK, the task name or a regex.
TEST, the test name or a regex.
THREADS, the thread level or a regex.
\b
You can use '' in place of VARIANT, TASK, TEST, THREADS if you want to match all. See the
examples.
\b
Examples:
    $> revision=bad5afd612e8fc917fb035d8333cffd7d68a37cc
\b
    # dry run mark all sys-perf points for a given revision
    $> change-points mark $revision sys-perf -n
\b
    # mark all sys-perf points for a given revision
    $> change-points mark $revision sys-perf
\b
    # mark all linux-1-node-replSet sys-perf points for a given revision
    $> change-points mark $revision sys-perf linux-1-node-replSet
\b
    # mark all replSet sys-perf points for a given revision
    $> change-points mark $revision sys-perf '/linux-.-node-replSet/'
\b
    # mark all non canary change_streams_latency linux-1-node-replSet sys-perf points for a given
    # revision
    $> change-points mark $revision sys-perf revision linux-1-node-replSet change_streams_latency
    --exclude '/^(fio_|canary_)/'
\b
    # mark all canary change_streams_latency linux-1-node-replSet sys-perf points for a given
    # revision
    $> change-points mark $revision sys-perf linux-1-node-replSet change_streams_latency \
       '/^(fio_|canary_)/'
\b
    #  mark all the revision sys-perf find_limit-useAgg 8 thread level
    $> change-points mark $revision sys-perf '' '' find_limit-useAgg 8
\b
    #  mark all the revision sys-perf find_limit-useAgg all thread level
    $> change-points mark $revision sys-perf '' '' find_limit-useAgg
    $> change-points mark $revision sys-perf '' '' find_limit-useAgg ''
"""
    query = process_params(revision, project, variant, task, test, thread_level)
    mark_change_points(PROCESSED_TYPE_ACKNOWLEDGED, query, process_excludes(exclude_patterns),
                       command_config)


@cli.command(name="hide")
@click.pass_obj
@click.option('--exclude', 'exclude_patterns',
              multiple=True,
              help='tests are excluded if this matches. It can be provided multiple times. ' +
              'A regex starts with a "/" char')
@click.argument('revision', required=True)
@click.argument('project', required=True)
@click.argument('variant', required=False)
@click.argument('task', required=False)
@click.argument('test', required=False)
@click.argument('thread_level', required=False)
def hide_command(command_config, exclude_patterns, revision, project, variant, task, test,
                 thread_level):
    # pylint: disable=too-many-arguments, too-many-function-args
    """
    Hide a change point(s). This process creates a copy of a change_points (ephemeral output of
the signal processing algorithm) in the (persistent) processed_change_point collection.

Arguments can be string or patterns, A pattern starts with /.

\b
REVISION, the revision of the change point. This parameter is mandatory.
PROJECT, the project name or a regex (like /^sys-perf-3.*/ or /^(sys-perf|performance)$/). This
parameter is mandatory.
VARIANT, the build variant or a regex.
TASK, the task name or a regex.
TEST, the test name or a regex.
THREADS, the thread level or a regex.
\b
You can use '' in place of VARIANT, TASK, TEST, THREADS if you want to match all. See the
examples.
\b
Examples:
    $> revision=bad5afd612e8fc917fb035d8333cffd7d68a37cc
\b
    # dry run on all sys-perf points for a given revision
    $> change-points hide $revision sys-perf -n
\b
    # hide sys-perf change points
    $> change-points hide $revision sys-perf
    $> change-points hide $revision sys-perf linux-1-node-replSet
    $> change-points hide $revision sys-perf '/linux-.-node-replSet/'
    $> change-points hide $revision sys-perf revision linux-1-node-replSet \\
       change_streams_latency  --exclude '/^(fio_|canary_)/'
    $> change-points hide $revision sys-perf linux-1-node-replSet change_streams_latency \\
    '/^(fio_|canary_)/'
\b
    #  hide all the revision sys-perf find_limit-useAgg 8 thread level
    $> change-points hide $revision sys-perf '' '' find_limit-useAgg 8
\b
    #  hide all the revision sys-perf find_limit-useAgg all thread level
    $> change-points hide  $revision sys-perf '' '' find_limit-useAgg
    $> change-points hide $revision sys-perf '' '' find_limit-useAgg ''
"""

    query = process_params(revision, project, variant, task, test, thread_level)
    mark_change_points(PROCESSED_TYPE_HIDDEN, query, process_excludes(exclude_patterns),
                       command_config)


@cli.command(name="update")
@click.pass_obj
@click.option('--exclude', 'exclude_patterns', multiple=True,
              help='Exclude all points matching this pattern. This parameter can be provided ' +
              'multiple times.')
@click.option('--processed_type',
              type=click.Choice(PROCESSED_TYPES),
              default=PROCESSED_TYPE_HIDDEN,
              required=True,
              help='The value to set processed_type.')
@click.argument('revision', required=True)
@click.argument('project', required=True)
@click.argument('variant', required=False)
@click.argument('task', required=False)
@click.argument('test', required=False)
@click.argument('thread_level', required=False)
def update_command(command_config, exclude_patterns, processed_type, revision, project, variant,
                   task, test, thread_level):
    # pylint: disable=too-many-arguments, too-many-function-args
    """
    Update an existing processed change point(s).
Arguments can be string or patterns, A pattern starts with /.

\b
REVISION, the revision of the change point. This parameter is mandatory.
PROJECT, the project name or a regex (like /^sys-perf-3.*/ or /^(sys-perf|performance)$/). This
parameter is mandatory.
VARIANT, the build variant or a regex.
TASK, the task name or a regex.
TEST, the test name or a regex.
THREADS, the thread level or a regex.
\b
You can use '' in place of VARIANT, TASK, TEST, THREADS if you want to match all. See the
examples.
\b
Examples:
    $> revision=bad5afd612e8fc917fb035d8333cffd7d68a37cc
\b
    # dry run on all sys-perf points
    $> change-points update $revision sys-perf -n
\b
    # update all *existing* sys-perf change points for a specific sys perf revision as hidden
    $> change-points update $revision sys-perf
\b
    # update some existing processed change point as acknowledged
    $> change-points update $revision sys-perf linux-1-node-replSet --processed_type acknowledged
    $> change-points update $revision sys-perf '/linux-.-node-replSet/' \\
    --processed_type acknowledged
    $> change-points update $revision sys-perf revision linux-1-node-replSet \\
    change_streams_latency --exclude '/^(fio_|canary_)/' --processed_type acknowledged
    $> change-points update $revision sys-perf linux-1-node-replSet change_streams_latency \\
       '/^(fio_|canary_)/' --processed_type acknowledged
\b
    #  hide all the revision sys-perf find_limit-useAgg 8 thread level
    $> change-points update  $revision sys-perf '' '' find_limit-useAgg 8 --processed_type hidden
    $> change-points update  $revision sys-perf '' '' find_limit-useAgg 8
\b
    #  update all the revision sys-perf find_limit-useAgg 8 thread level as acknowledged
    $> change-points update  $revision sys-perf '' '' find_limit-useAgg 8 \\
    --processed_type acknowledged
\b
    #  hide all the revision sys-perf find_limit-useAgg all thread level
    $> change-points update $revision sys-perf '' '' find_limit-useAgg --processed_type hidden
    $> change-points update $revision sys-perf '' '' find_limit-useAgg
\b
    #  update all the revision sys-perf find_limit-useAgg all thread level as acknowledgedreal
    $> change-points update $revision sys-perf '' '' find_limit-useAgg '' \\
    --processed_type acknowledged
"""
    query = process_params(revision, project, variant, task, test, thread_level)
    update_change_points(processed_type, query, process_excludes(exclude_patterns), command_config)


@cli.command(name="list")
@click.pass_obj
@click.option('--exclude', 'exclude_patterns',
              multiple=True,
              help='tests are excluded if this matches. It can be provided multiple times. ' +
              'A regex starts with a "/" char')
@click.option('--processed/--no-processed', default=False, help='The type of point to list.')
@click.argument('revision', required=False)
@click.argument('project', required=False)
@click.argument('variant', required=False)
@click.argument('task', required=False)
@click.argument('test', required=False)
@click.argument('thread_level', required=False)
def list_command(command_config, exclude_patterns, processed, revision, project, variant, task,
                 test, thread_level):
    # pylint: disable=too-many-arguments, too-many-function-args

    """
    List points (defaults to change points).

Arguments can be string or patterns, A pattern starts with /.

\b
REVISION, the revision of the change point.
PROJECT, the project name or a regex (like /^sys-perf-3.*/ or /^(sys-perf|performance)$/).
VARIANT, the build variant or a regex.
TASK, the task name or a regex.
TEST, the test name or a regex.
THREADS, the thread level or a regex.
\b
You can use '' in place of VARIANT, TASK, TEST, THREADS if you want to match all. See the
examples.
\b
Examples:
    $> revision=bad5afd612e8fc917fb035d8333cffd7d68a37cc
\b
    # list all change points
    $> change-points list
    $> change-points list --no-processed
\b
    # list all processed change points
    $> change-points list --processed
\b
    # list change points for a revision
    $> change-points list $revision
\b
    # list sys perf change points for a revision
    $> change-points list $revision sys-perf # list all sys-perf points for revision
\b
    # list sys perf change points (any revision)
    $> change-points list '' sys-perf
\b
    # list change points matching criteria
    $> change-points list $revision sys-perf linux-1-node-replSet
    $> change-points list $revision sys-perf '/linux-.-node-replSet/'
\b
    # list non canary change points for sys-perf linux-1-node-replSet change_streams_latency
    # and revision
    $> change-points list $revision sys-perf linux-1-node-replSet change_streams_latency \\
    '/^(fio_|canary_|Network)/'
\b
    # list all non canary change points for sys-perf linux-1-node-replSet change_streams_latency
    # and revision
    $> change-points list $revision sys-perf linux-1-node-replSet change_streams_latency \\
    --exclude '/^(fio_|canary_|Network)/'
\b
    # list all the sys-perf find_limit-useAgg (any revision)
    $> change-points list '' sys-perf '' '' find_limit-useAgg
"""
    query = process_params(revision, project, variant, task, test, thread_level)
    list_change_points(processed, query, process_excludes(exclude_patterns), command_config)
