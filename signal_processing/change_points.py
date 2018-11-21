#!/usr/bin/env python2.7
"""
Cli wrapper for various change point operations

To get access to the help try the following command:

    $> change-points help
"""
# TODO: remove the following line on completion of PERF-1608.
# pylint: disable=too-many-lines

from __future__ import print_function

import multiprocessing
import os
from StringIO import StringIO
from collections import OrderedDict
from datetime import datetime

import click
import structlog
import yaml

import signal_processing.commands.compare as compare
import signal_processing.commands.compute as compute
import signal_processing.commands.helpers as helpers
import signal_processing.commands.jobs as jobs
import signal_processing.commands.list_build_failures as list_build_failures
import signal_processing.commands.list_change_points as list_change_points
import signal_processing.commands.list_failures as list_failures
import signal_processing.commands.manage as manage
import signal_processing.commands.mark as mark
import signal_processing.commands.unmark as unmark
import signal_processing.commands.update as update
import signal_processing.commands.visualize as visualize
import signal_processing.qhat as qhat
from signal_processing import detect_changes
from analysis.evergreen import evergreen_client
from bin.common import log

DB = 'perf'
PROCESSED_CHANGE_POINTS = 'processed_change_points'
CHANGE_POINTS = 'change_points'
POINTS = 'points'
BUILD_FAILURES = 'build_failures'

LOG = structlog.getLogger(__name__)

APP_NAME = os.environ.get('DSI_APP_NAME', 'change-points')
"""
The name to use to look for the application configuration. Don't change
from the default 'change-points' unless you have a compelling reason or
you want to test.
"""

APP_CONF_LOCATION = os.environ.get('DSI_APP_CONF_LOCATION', None)
"""
The config files are looked up in the following locations (in the following order):
  1. The current directory.
  1. The DSI_APP_CONF_LOCATION env var.
  1. The direcory returned from click.get_app_dir with force_posix set to True.
See `click.get_app_dir<http://click.pocoo.org/5/api/#click.get_app_dir>'.
"""

CONTEXT_SETTINGS = dict(
    default_map=helpers.read_default_config(APP_NAME, APP_CONF_LOCATION),
    help_option_names=['-h', '--help'],
    max_content_width=120)


@click.group(context_settings=CONTEXT_SETTINGS, invoke_without_command=True)
@click.option(
    '-d', '--debug', count=True, help='Enable debug output, you can pass multiple -ddddd etc.')
@click.option('-l', '--logfile', default=None, help='The log file to write to, defaults to None.')
@click.option('-o', '--out', default='/tmp', help='The location to save any files in.')
@click.option(
    '-f', '--format', 'file_format', default='png', help='The format to save any files in.')
@click.option(
    '-u',
    '--mongo-uri',
    default='mongodb://localhost:27017/' + DB,
    help='MongoDB connection string. The database name comes from here too.',
    envvar="DSI_MONGO_URI")
@click.option('-q', '--queryable', default=False, help='Print ids as queries')
@click.option('-n', '--dry-run', is_flag=True, default=False, help='Do not actually run anything.')
@click.option(
    '-c', '--compact/--expanded', 'compact', default=True, help='Display objects one / line.')
@click.option(
    '--style', default=['bmh'], multiple=True, help='The default matplot lib style to use.')
@click.option('--token-file', default=None, envvar='DSI_TOKEN_FILE')
@click.option('--mongo-repo', 'mongo_repo', default='~/src', envvar='DSI_MONGO_REPO')
@click.pass_context
def cli(context, debug, logfile, out, file_format, mongo_uri, queryable, dry_run, compact, style,
        token_file, mongo_repo):
    """
For a list of styles see 'style sheets<https://matplotlib.org/users/style_sheets.html>'.

You can create a config file to hold commonly used config parameters.

The CLI looks for configuration files in the following locations (int his order):

\b
1. ./.change-points
2. ${DSI_APP_CONF_LOCATION}/.change-points.
3. ~/.change-points or whatever is returned by
[click_get_app_dir](http://click.pocoo.org/5/api/#click.get_app_dir) for your OS.

The file is assumed to be yaml. A sample config file looks like:

\b
# -*-yaml-*-
# Enable debug if debug > 0, you can set higher levels.
debug: 0
# The log file to write to, defaults to None.
logfile: /tmp/change-points.log
# MongoDB connection string. The database name comes from here too.
mongo_uri: mongodb://localhost/perf
# Possible styles are list at https://matplotlib.org/users/style_sheets.html
# 'style' is an array and you can provide multiple values.
style:
  - bmh
token_file: ./config.yml
mongo_repo: ~/git/mongo-for-hashes
# The following sections are for the sub commands.
# These are over laid on the cli params (above).
compare:
  progressbar: false
  no_older_than: 14
  show: true
compute:
  # Note: Don't add help to a command as it would be confusing. It will
  # always just print help and exit.
  progressbar: true
list:
  limit: 20
  no_older_than: 20
list-build-failures:
  human_readable: true
mark:
  exclude_patterns:
    - this
    - that
update:
  exclude:
    - this
    - that
visualize:
  sigma: 2.0

__Note:__ dashes on the command names (e.g. 'list-build-failures') and underscores on the
field names ('human_readable').

The configuration values are applied in the following order:

\b
   1. Defaults as defined in the help.
   2. Values specified in the configuration file.
   3. Values in an env var (if applicable).
   4. Command line parameter values.


"""
    # pylint: disable=missing-docstring, too-many-arguments, too-many-locals
    config = helpers.CommandConfiguration(
        debug=debug,
        out=out,
        log_file=logfile,
        file_format=file_format,
        mongo_uri=mongo_uri,
        queryable=queryable,
        dry_run=dry_run,
        compact=compact,
        style=style,
        token_file=token_file,
        mongo_repo=mongo_repo)
    context.obj = config
    if context.invoked_subcommand is None:
        print(context.get_help())
    log.setup_logging(config.debug > 0, filename=config.log_file)


@cli.command(name='help')
@click.pass_context
def help_command(context):
    """
    Show the help message and exit.
    """
    print(context.parent.get_help())


@cli.command(name='mark')
@click.pass_obj
@click.option(
    '--exclude',
    'exclude_patterns',
    multiple=True,
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

Arguments can be strings or patterns, A pattern starts with /.

\b
REVISION, the revision of the change point. This parameter is mandatory.
PROJECT, the project name or a regex (like /^sys-perf-3.*/ or /^(sys-perf|performance)$/). This
parameter is mandatory.
VARIANT, the build variant or a regex.
TASK, the task name or a regex.
TEST, the test name or a regex.
THREADS, the thread level or a regex.
\b
You can use '' in place of VARIANT, TASK, TEST, THREADS if you want to match all. See the examples.
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
    query = helpers.process_params(revision, project, variant, task, test, thread_level)
    mark.mark_change_points(helpers.PROCESSED_TYPE_ACKNOWLEDGED, query,
                            helpers.process_excludes(exclude_patterns), command_config)


@cli.command(name='hide')
@click.pass_obj
@click.option(
    '--exclude',
    'exclude_patterns',
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

    query = helpers.process_params(revision, project, variant, task, test, thread_level)
    mark.mark_change_points(helpers.PROCESSED_TYPE_HIDDEN, query,
                            helpers.process_excludes(exclude_patterns), command_config)


@cli.command(name='update')
@click.pass_obj
@click.option(
    '--exclude',
    'exclude_patterns',
    multiple=True,
    help='Exclude all points matching this pattern. This parameter can be provided ' +
    'multiple times.')
@click.option(
    '--processed-type',
    'processed_type',
    type=click.Choice(helpers.PROCESSED_TYPES),
    default=helpers.PROCESSED_TYPE_HIDDEN,
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
    $> change-points update $revision sys-perf linux-1-node-replSet --processed-type acknowledged
    $> change-points update $revision sys-perf '/linux-.-node-replSet/' \\
    --processed-type acknowledged
    $> change-points update $revision sys-perf revision linux-1-node-replSet \\
    change_streams_latency --exclude '/^(fio_|canary_)/' --processed-type acknowledged
    $> change-points update $revision sys-perf linux-1-node-replSet change_streams_latency \\
       '/^(fio_|canary_)/' --processed-type acknowledged
\b
    #  hide all the revision sys-perf find_limit-useAgg 8 thread level
    $> change-points update  $revision sys-perf '' '' find_limit-useAgg 8 --processed-type hidden
    $> change-points update  $revision sys-perf '' '' find_limit-useAgg 8
\b
    #  update all the revision sys-perf find_limit-useAgg 8 thread level as acknowledged
    $> change-points update  $revision sys-perf '' '' find_limit-useAgg 8 \\
    --processed-type acknowledged
\b
    #  hide all the revision sys-perf find_limit-useAgg all thread level
    $> change-points update $revision sys-perf '' '' find_limit-useAgg --processed-type hidden
    $> change-points update $revision sys-perf '' '' find_limit-useAgg
\b
    #  update all the revision sys-perf find_limit-useAgg all thread level as acknowledgedreal
    $> change-points update $revision sys-perf '' '' find_limit-useAgg '' \\
    --processed-type acknowledged
"""
    query = helpers.process_params(revision, project, variant, task, test, thread_level)
    update.update_change_points(processed_type, query, helpers.process_excludes(exclude_patterns),
                                command_config)


@cli.command(name='unmark')
@click.pass_obj
@click.option(
    '--exclude',
    'exclude_patterns',
    multiple=True,
    help='Exclude all points matching this pattern. This parameter can be provided ' +
    'multiple times.')
@click.option(
    '--processed-type',
    'processed_type',
    type=click.Choice(['any'] + helpers.PROCESSED_TYPES),
    default='any',
    required=True,
    help='The value to set processed_type.')
@click.argument('revision', required=True)
@click.argument('project', required=True)
@click.argument('variant', required=False)
@click.argument('task', required=False)
@click.argument('test', required=False)
@click.argument('thread_level', required=False)
def unmark_command(command_config, exclude_patterns, processed_type, revision, project, variant,
                   task, test, thread_level):
    # pylint: disable=too-many-arguments, too-many-function-args
    """
    Unmark (Delete) an existing processed change point(s).
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
    $> change-points unmark $revision sys-perf -n
\b
    # unmark all *existing* sys-perf change points for a specific sys perf revision
    $> change-points unmark $revision sys-perf
\b
    # unmark some existing acknowledged processed change points
    $> change-points unmark $revision sys-perf linux-1-node-replSet --processed-type acknowledged
    $> change-points unmark $revision sys-perf '/linux-.-node-replSet/' \\
    --processed-type acknowledged
    $> change-points unmark $revision sys-perf revision linux-1-node-replSet \\
    change_streams_latency --exclude '/^(fio_|canary_)/' --processed-type acknowledged
    $> change-points unmark $revision sys-perf linux-1-node-replSet change_streams_latency \\
       '/^(fio_|canary_)/' --processed-type acknowledged
\b
    # unmark all hidden points matching revision sys-perf find_limit-useAgg 8 thread level
    $> change-points unmark  $revision sys-perf '' '' find_limit-useAgg 8 --processed-type hidden
    #  unmark all points matching revision sys-perf find_limit-useAgg 8 thread level
    $> change-points unmark  $revision sys-perf '' '' find_limit-useAgg 8
\b
    # unmark all acknowledged points matching revision sys-perf find_limit-useAgg 8 thread level as
    # acknowledged
    $> change-points update  $revision sys-perf '' '' find_limit-useAgg 8 \\
    --processed-type acknowledged
\b
    # unmark all hidden points matching revision sys-perf find_limit-useAgg all thread level
    $> change-points update $revision sys-perf '' '' find_limit-useAgg --processed-type hidden
    #  unmark all points matching revision sys-perf find_limit-useAgg all thread level
    $> change-points update $revision sys-perf '' '' find_limit-useAgg
\b
    # unmark all acknowledged revision sys-perf find_limit-useAgg all thread level as acknowledged
    $> change-points update $revision sys-perf '' '' find_limit-useAgg '' \\
    --processed-type acknowledged
"""
    query = helpers.process_params(revision, project, variant, task, test, thread_level)
    unmark.unmark_change_points(None if processed_type == 'any' else processed_type, query,
                                helpers.process_excludes(exclude_patterns), command_config)


@cli.command(name='list')
@click.pass_obj
@click.option(
    '--exclude',
    'exclude_patterns',
    multiple=True,
    help='tests are excluded if this matches. It can be provided multiple times. ' +
    'A regex starts with a "/" char')
@click.option(
    '--point-type',
    type=click.Choice(list_change_points.VALID_CHANGE_POINT_TYPES),
    default=list_change_points.CHANGE_POINT_TYPE_UNPROCESSED,
    help='The type of point to list.')
@click.option(
    '--limit',
    callback=helpers.validate_int_none_options,
    default='10',
    help='''The maximum number of change points to display.
    The default is 10. Use \'None\' for no limit.''')
@click.option(
    '--no-older-than',
    callback=helpers.validate_int_none_options,
    default='14',
    help='''Don't consider points older than this number of days.
A perf BB rotation is 2 weeks, so 14 days seems appropriate''')
@click.option(
    '--human-readable/--no-human-readable',
    'human_readable',
    is_flag=True,
    default=True,
    help='Print output in a more human-friendly output.')
@click.option(
    '--show-canaries/--hide-canaries',
    'show_canaries',
    is_flag=True,
    default=False,
    help='Should canaries be shown (defaults to hidden). The filtering happens in the database.')
@click.option(
    '--processed-type',
    'processed_types',
    type=click.Choice(helpers.PROCESSED_TYPES),
    default=[helpers.PROCESSED_TYPE_ACKNOWLEDGED],
    required=False,
    multiple=True,
    help='When displaying the processed list, the processed_type must be one of the supplied types.'
)
@click.option(
    '--show-wtdevelop/--hide-wtdevelop',
    'show_wtdevelop',
    is_flag=True,
    default=False,
    help='Should wtdevelop be shown (defaults to hidden). The filtering happens in the database.')
@click.option('--revision', 'revision', default=None, help='Specify a revision, defaults to None.')
@click.argument('project', required=False)
@click.argument('variant', required=False)
@click.argument('task', required=False)
@click.argument('test', required=False)
@click.argument('thread_level', required=False)
def list_command(command_config, exclude_patterns, point_type, limit, no_older_than, human_readable,
                 show_canaries, show_wtdevelop, processed_types, revision, project, variant, task,
                 test, thread_level):
    # pylint: disable=too-many-arguments, too-many-locals, too-many-function-args
    """
    List unprocessed / processed or raw change points (defaults to unprocessed).
The points are grouped by revision and project to reduce clutter. The default is to only show groups
with a change point in the last 14 days. (use --no-older-than=None for all or --no-older-than=30 to
view older change points). The points are sorted by the min magnitude (ascending) of change. By
default, the backing aggregation removes canary test or wtdevelop tasks. These can be viewed with
the --show-canaries or --show-wtdevelop options. The output defaults to human readable format (which
is also valid markdown).

Arguments can be string or patterns, A pattern starts with /.

\b
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
    # list unprocessed change points
    $> change-points list                           # list 10
    $> change-points list --point-type unprocessed  # list 10
    $> change-points list --limit None              # list all
\b
    # list processed change points
    $> change-points list --point-type processed
\b
    # list change points
    $> change-points list --point-type raw
\b
    # list unprocessed change points for a revision
    $> change-points list --revision $revision
\b
    # list sys perf unprocessed change points for a revision
    $> change-points list sys-perf --revision $revision # list all sys-perf points for revision
\b
    # list sys perf unprocessed change points (any revision)
    $> change-points list sys-perf
\b
    # list unprocessed change points matching criteria
    $> change-points list revision sys-perf linux-1-node-replSet --revision $revision
    $> change-points list sys-perf '/linux-.-node-replSet/' --revision $revision
\b
    # list non canary unprocessed change points for sys-perf linux-1-node-replSet
    # change_streams_latency and revision
    $> change-points list sys-perf linux-1-node-replSet change_streams_latency \\
    '/^(fio_|canary_|Network)/' --revision $revision
\b
    # list all non canary unprocessed change points for sys-perf linux-1-node-replSet
    # change_streams_latency and revision
    $> change-points list sys-perf linux-1-node-replSet change_streams_latency \\
    --exclude '/^(fio_|canary_|Network)/' --revision $revision
\b
    # list all the unprocessed sys-perf find_limit-useAgg (any revision)
    $> change-points list sys-perf '' '' find_limit-useAgg
\b
    # list all the acknowledged processed sys-perf change points
    $> change-points list sys-perf  --point-type processed --processed-type acknowledged
    $> change-points list sys-perf  --point-type processed
\b
    # list all the hidden processed sys-perf change points
    $> change-points list sys-perf  --point-type processed --processed-type hidden
\b
    # list all the processed sys-perf change points
    $> change-points list sys-perf  --point-type processed --processed-type acknowledged\
    --processed-type hidden
"""
    query = helpers.process_params(revision, project, variant, task, test, thread_level)
    list_change_points.list_change_points(
        change_point_type=point_type,
        query=query,
        limit=limit,
        no_older_than=no_older_than,
        human_readable=human_readable,
        hide_canaries=not show_canaries,
        hide_wtdevelop=not show_wtdevelop,
        exclude_patterns=helpers.process_excludes(exclude_patterns),
        processed_types=processed_types,
        command_config=command_config)


@cli.command(name='compare')
@click.pass_obj
@click.option('-m', '--minsize', 'minsizes', default=[20], type=click.INT, multiple=True)
@click.option('-s', '--sig', 'sig_lvl', default=.05)
@click.option('-p', '--padding', default=0, help='append this many repetitions of the last result.')
@click.option(
    '--minimum',
    callback=helpers.validate_int_none_options,
    default=detect_changes.DEFAULT_MIN_SIZE,
    help='The minimum number of points to process. None or zero for all points.')
@click.option('--progressbar/--no-progressbar', default=True)
@click.option('--show/--no-show', default=False)
@click.option('--save/--no-save', default=False)
@click.option('--exclude', 'excludes', multiple=True)
@click.option(
    '--no-older-than',
    default=30,
    help='exclude tasks that have no points newer than this number of days.')
@click.option('--weighting', 'weighting', default=qhat.DEFAULT_WEIGHTING)
@click.argument('project', required=False)
@click.argument('variant', required=False)
@click.argument('task', required=False)
@click.argument('test', required=False)
def compare_command(command_config, minsizes, sig_lvl, padding, minimum, progressbar, show, save,
                    excludes, no_older_than, weighting, project, variant, task, test):
    # pylint: disable=too-many-locals, too-many-arguments, line-too-long
    """
Compare points generated from R and python. This requires R and the ecp library to be installed.

\b
PROJECT, the project name or a regex (like /^sys-perf-3.*/ or /^(sys-perf|performance)$/).
VARIANT, the build variant or a regex.
TASK, the task name or a regex.
TEST, the test name or a regex.

\b
Examples:
    # dry run compare all sys-perf change points
    $> change-points -n compare sys-perf  # dry run on all sys-perf points
    # compare all sys-perf change points (with and without a progressbar)
    $> change-points compare sys-perf
    $> change-points compare sys-perf --no-progressbar
\b
    # compare all linux-1-node-replSet sys-perf change points
    $> change-points compare sys-perf linux-1-node-replSet
    # compare all linux replSet sys-perf change points
    $> change-points compare sys-perf '/linux-.-node-replSet/'
    # compare all change_streams_latency linux 1 node replSet sys-perf change points  excluding
    # canary type tests
    $> change-points compare sys-perf linux-1-node-replSet change_streams_latency \
       --exclude '/^(fio_|canary_|NetworkBandwidth)/'
    # compare only canary change_streams_latency linux 1 node replSet sys-perf change points
    $> change-points compare sys-perf linux-1-node-replSet change_streams_latency \
       '/^(fio_|canary_|NetworkBandwidth)/'

\b
See also the help for the base for extra parameters.
\b
For Example:
    $> change-points -n compare sys-perf
\b
    # save png images to ~/tmp/
    $> change-points -o ~/tmp compare sys-perf --save
    # save svg images to ~/tmp/
    $> change-points -o ~/tmp -f svg compare sys-perf --save
\b
    # padding and minsize on r / py change points
\b
    # padding appends the last point, it may be useful in finding change points close to the
    # right hand side but it can affect the average so may affect older change points
    # padding affects both R and Py.
    $> change-points compare sys-perf linux-1-node-replSet bestbuy_query \\
       count_with_and_predicate-noAgg  --show
    $> change-points compare sys-perf linux-1-node-replSet bestbuy_query\\
       --show  --exclude '/^(?!count_with_and_predicate-noAgg)/' -p 20
    $> change-points compare sys-perf linux-1-node-replSet bestbuy_query \\
       count_with_and_predicate-noAgg  --show   -p 20
\b
    # m only affects R, it may help find more recent change points. But will probably result in
    # more change points overall too.
    # Lower values seem to be better at finding large changes.
    $> change-points compare sys-perf linux-1-node-replSet bestbuy_query \\
       count_with_and_predicate-noAgg  --show  -m5
    $> change-points compare sys-perf linux-1-node-replSet bestbuy_query \\
       count_with_and_predicate-noAgg  --show  -m10 -p10
    # p should probably be no larger than m / 2
    $> change-points compare sys-perf linux-1-node-replSet bestbuy_query \\
       count_with_and_predicate-noAgg  --show  -m10 -p5
    $> change-points compare sys-perf linux-1-node-replSet bestbuy_query \\
       count_with_and_predicate-noAgg  --show  -m10
    $> change-points compare sys-perf linux-1-node-replSet bestbuy_query \\
       count_with_and_predicate-noAgg  --show  -p10
    $> change-points compare sys-perf linux-1-node-replSet bestbuy_query \\
       count_with_and_predicate-noAgg  --show  -p20
"""
    # pylint: enable=line-too-long
    LOG.debug('starting')
    points = command_config.points

    query = helpers.process_params(None, project, variant, task, test, None)
    LOG.debug('processed params', query=query)

    matching_tasks = helpers.filter_legacy_tasks(
        helpers.get_matching_tasks(points, query, no_older_than))
    LOG.debug('matched tasks', matching_tasks=matching_tasks)

    exclude_patterns = helpers.process_excludes(excludes)
    tests = [
        test_identifier for test_identifier in helpers.generate_tests(matching_tasks)
        if not helpers.filter_tests(test_identifier['test'], exclude_patterns)
    ]
    LOG.debug('matched tests', tests=tests)

    test_identifiers = [
        thread_identifier
        for test_identifier in tests for thread_identifier in helpers.generate_thread_levels(
            test_identifier, command_config.points)
    ]

    all_calculations = []
    group_by_task = OrderedDict()
    group_by_test = OrderedDict()

    label = 'Compare'

    bar_template, show_label = helpers.query_terminal_for_bar()
    with click.progressbar(test_identifiers,
                           label=label,
                           item_show_func=show_label,
                           file=None if progressbar else StringIO(),
                           bar_template=bar_template) as progress: # yapf: disable

        for test_identifier in progress:
            project = test_identifier['project']
            variant = test_identifier['variant']
            task_name = test_identifier['task']
            test_name = test_identifier['test']
            progress.label = test_name
            progress.render_progress()
            try:
                LOG.debug('compare', test_identifier=test_identifier)
                calculation = compare.compare(
                    test_identifier,
                    minimum,
                    command_config,
                    sig_lvl=sig_lvl,
                    minsizes=minsizes,
                    padding=padding,
                    weighting=weighting)
                all_calculations.append(calculation)
                identifier = (project, variant, task_name)
                if identifier not in group_by_task:
                    group_by_task[identifier] = []
                group_by_task[identifier].append(calculation)

                identifier = (project, variant, task_name, test_name)
                if identifier not in group_by_test:
                    group_by_test[identifier] = []
                group_by_test[identifier].append(calculation)
            except KeyError:
                LOG.error('unexpected error', exc_info=1)

    for task_identifier, calculations in group_by_task.items():
        project, variant, task_name = task_identifier
        print('{{ project: {}, variant: {}, task: {} }}'.format(project, variant, task_name))

        for result in calculations:
            compare.print_result(result, command_config)

    import matplotlib.pyplot as plt
    with plt.style.context(command_config.style):
        if not command_config.dry_run and save or show:
            for test_identifier, results in group_by_test.items():
                compare.plot_test(save, show, test_identifier, results, padding, sig_lvl, minsizes,
                                  command_config.out, command_config.file_format)


@cli.command(name='compute')
@click.pass_context
@click.option(
    '--exclude',
    'excludes',
    multiple=True,
    help='Exclude all points matching this pattern. This parameter can be provided multiple times.')
@click.option('--progressbar/--no-progressbar', default=True)
@click.option(
    '--minimum',
    callback=helpers.validate_int_none_options,
    default=detect_changes.DEFAULT_MIN_SIZE,
    help='The minimum number of points to process. None or zero for all points.')
@click.option('--weighting', default=.001)
@click.option(
    '--pool-size',
    default=max(multiprocessing.cpu_count() - 1, 1),
    help='Set the process pool size. The default is the number of cores -1.')
@click.option(
    '--legacy/--no-legacy', default=False, help='Enable creation of legacy change points.')
@click.argument('project', required=True)
@click.argument('variant', required=False)
@click.argument('task', required=False)
@click.argument('test', required=False)
@click.argument('thread_level', required=False)
def compute_command(context, excludes, progressbar, minimum, weighting, pool_size, legacy, project,
                    variant, task, test, thread_level):
    # pylint: disable=too-many-locals, too-many-arguments, line-too-long
    """
Compute / recompute change point(s). This deletes and then replaces the current change points
for the matching tasks.

Arguments can be strings or patterns, A pattern starts with /.

\b
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
    # dry run compute all sys-perf change points
    $> change-points compute sys-perf -n
\b
    # compute all sys-perf change points
    $> change-points compute sys-perf
\b
    # compute all performance change points with a minimum number of data points.
    $> change-points compute sys-perf --minimum 500
    $> change-points compute sys-perf
\b
    # compute all performance change points with all data points
    $> change-points compute sys-perf --minimum 0
\b
    # compute all performance change points from the first change point forward
    $> change-points compute sys-perf --minimum 1
\b
    # compute linux-1-node-replSet sys-perf change points
    $> change-points compute sys-perf linux-1-node-replSet
\b
    # compute replSet sys-perf change points
    $> change-points compute sys-perf '/linux-.-node-replSet/'
\b
    # compute non canary change_streams_latency linux-1-node-replSet sys-perf change points
    $> change-points compute sys-perf revision linux-1-node-replSet change_streams_latency
    --exclude '/^(fio_|canary_)/'
\b
    # compute canary change_streams_latency linux-1-node-replSet sys-perf change points
    $> change-points compute sys-perf linux-1-node-replSet change_streams_latency \
       '/^(fio_|canary_)/'
\b
    #  compute the revision sys-perf find_limit-useAgg
    $> change-points compute sys-perf '' '' find_limit-useAgg
"""
    # pylint: disable=too-many-locals, too-many-branches
    LOG.debug('starting')
    command_config = context.obj
    points = command_config.points
    query = helpers.process_params(None, project, variant, task, test, thread_level)

    LOG.debug('finding matching tasks', query=query)
    matching_tasks = helpers.get_matching_tasks(points, query)
    if not legacy:
        matching_tasks = helpers.filter_legacy_tasks(matching_tasks)
    else:
        matching_tasks = list(matching_tasks)

    LOG.debug('finding matching tests in tasks', matching_tasks=matching_tasks)
    exclude_patterns = helpers.process_excludes(excludes)
    tests = list(
        test_identifier for test_identifier in helpers.generate_tests(matching_tasks)
        if not helpers.filter_tests(test_identifier['test'], exclude_patterns))

    test_identifiers = [
        thread_identifier
        for test_identifier in tests for thread_identifier in helpers.generate_thread_levels(
            test_identifier, command_config.points, thread_level=query.get('thread_level', None))
    ]

    label = 'compute'

    start_time = datetime.utcnow()
    LOG.debug('finding matching tests in tasks', tests=tests)
    # It is useful for profiling (and testing) to be able to run in a single process
    job_list = [
        jobs.Job(
            compute.compute_change_points,
            arguments=(test_identifier, weighting, command_config),
            kwargs=dict(min_points=minimum),
            identifier=test_identifier) for test_identifier in test_identifiers
    ]
    bar_template, show_item = helpers.query_terminal_for_bar()
    completed_jobs = jobs.process_jobs(
        job_list,
        pool_size=pool_size,
        label=label,
        progressbar=progressbar,
        bar_template=bar_template,
        show_item=show_item,
        key='test')
    jobs_with_exceptions = [job for job in completed_jobs if job.exception is not None]

    LOG.info("computed change points", duration=str(datetime.utcnow() - start_time))
    jobs.handle_exceptions(context, jobs_with_exceptions, command_config.log_file)


@cli.command(name='manage')
@click.pass_obj
def manage_command(command_config):
    # pylint: disable=too-many-locals, too-many-arguments, line-too-long
    """
Manage the infrastructural elements of the performance database. That is, indexes,
views etc.

\b
At the moment, it supports:
        1. The unprocessed change points view.
        2. The linked build failures view.
        3. The indexes for the point collection.
"""
    LOG.debug('starting')
    manage.manage(command_config)


@cli.command(name='visualize')
@click.pass_context
@click.option('--progressbar/--no-progressbar', default=True)
@click.option('--show/--no-show', default=True)
@click.option('--save/--no-save', default=False)
@click.option(
    '--qhat/--no-qhat',
    'show_qhat',
    default=False,
    help="If set to true then display the qhat values for the change points.")
@click.option('--exclude', 'excludes', multiple=True)
@click.option('--sigma', 'sigma', default=1.0)
@click.option('--filter', 'filter_type', default='butter')
@click.option('--only-change-points/--no-only-change-points', 'only_change_points', default=True)
@click.option(
    '--minimum',
    callback=helpers.validate_int_none_options,
    default=detect_changes.DEFAULT_MIN_SIZE,
    help='The minimum number of points to process. None or zero for all points.')
@click.option('--show-outliers/--no-show-outliers', 'show_outliers', default=True)
@click.option('--outlier-limit', 'outlier_limit', default=visualize.DEFAULT_OUTLIER_LIMIT)
@click.argument('project', required=False)
@click.argument('variant', required=False)
@click.argument('task', required=False)
@click.argument('test', required=False)
@click.argument('thread_level', required=False)
def visualize_command(context, progressbar, show, save, show_qhat, excludes, sigma, filter_type,
                      only_change_points, minimum, show_outliers, outlier_limit, project, variant,
                      task, test, thread_level):
    # pylint: disable=too-many-locals, too-many-arguments, line-too-long
    """
Note : this command is an optional command, provided as is and is liable to change or break.
You must install the Plotting requirements for it to work.

\b
    $> pip install -e .[Plotting]
    $> pip install 'git+https://github.com/10gen/dsi.git#egg=DSI[Plotting]'
\b
Visualize performance data and change points.

Arguments can be strings or patterns, A pattern starts with /.
\b
PROJECT, the project name or a regex (like /^sys-perf-3.*/ or /^(sys-perf|performance)$/).
VARIANT, the build variant or a regex.
TASK, the task name or a regex.
TEST, the test name or a regex.

\b
Examples:
    # visualize all sys-perf change points (with and without a progressbar)
    $> change-points visualize sys-perf
    $> change-points visualize sys-perf --no-progressbar
\b
    # visualize all linux-1-node-replSet sys-perf change points
    $> change-points visualize sys-perf linux-1-node-replSet
    # visualize all linux replSet sys-perf change points
    $> change-points visualize sys-perf '/linux-.-node-replSet/'
    # visualize all change_streams_latency linux 1 node replSet sys-perf change points  excluding
    # canary type tests
    $> change-points visualize sys-perf linux-1-node-replSet change_streams_latency \
       --exclude '/^(fio_|canary_|NetworkBandwidth)/'
    # visualize only canary change_streams_latency linux 1 node replSet sys-perf change points
    $> change-points visualize sys-perf linux-1-node-replSet change_streams_latency \
       '/^(fio_|canary_|NetworkBandwidth)/'

\b
See also the help for the base for extra parameters.
\b
For Example:
    $> change-points -n visualize sys-perf
\b
    # save png images to ~/tmp/
    $> change-points -o ~/tmp visualize sys-perf --save
    # save svg images to ~/tmp/
    $> change-points -o ~/tmp -f svg visualize sys-perf --save
"""
    # pylint: enable=line-too-long
    command_config = context.obj

    # The visualize command is optional. The requirements are not installed
    # by default as there can be issues on some OSes.
    # See the help message in the following block for installation
    # instructions.
    try:
        import matplotlib.pyplot as plt
    except:  # pylint: disable=bare-except
        message = 'matplotlib dependency is missing.'
        help_message = '''
Have you installed the optional `Plotting` requirements?

$> pip install -e .[Plotting]
$> pip install 'git+https://github.com/10gen/dsi.git#egg=DSI[Plotting]'
'''

        LOG.warn(message, help_message=help_message, exc_info=1)
        context.fail('{}{}'.format(message, help_message))

    LOG.debug('starting')
    points = command_config.points

    query = helpers.process_params(None, project, variant, task, test, thread_level)
    LOG.debug('processed params', query=query)

    matching_tasks = helpers.filter_legacy_tasks(helpers.get_matching_tasks(points, query))
    LOG.debug('matched tasks', matching_tasks=matching_tasks)

    exclude_patterns = helpers.process_excludes(excludes)
    tests = [
        test_identifier for test_identifier in helpers.generate_tests(matching_tasks)
        if not helpers.filter_tests(test_identifier['test'], exclude_patterns)
    ]
    LOG.debug('matched tests', tests=tests)

    test_identifiers = [
        thread_identifier
        for test_identifier in tests for thread_identifier in helpers.generate_thread_levels(
            test_identifier, command_config.points, thread_level=query.get('thread_level', None))
    ]

    label = 'visualize'

    bar_template, show_label = helpers.query_terminal_for_bar()

    with plt.style.context(command_config.style):
        with click.progressbar(test_identifiers,
                               label=label,
                               item_show_func=show_label,
                               file=None if progressbar else StringIO(),
                               bar_template=bar_template) as progress:# yapf: disable
            figure = None
            for test_identifier in progress:
                test_name = test_identifier['test']
                thread_level = test_identifier['thread_level']
                progress.label = test_name
                progress.render_progress()
                try:
                    LOG.debug('visualize', test_identifier=test_identifier)
                    for figure in visualize.visualize(
                            test_identifier,
                            minimum,
                            filter_type,
                            command_config,
                            sigma=sigma,
                            only_change_points=only_change_points,
                            show_qhat=show_qhat,
                            show_outliers=show_outliers,
                            outlier_limit=outlier_limit): # yapf: disable
                        if save:
                            pathname = os.path.join(command_config.out, test_identifier['project'],
                                                    test_identifier['variant'],
                                                    test_identifier['task'])

                            filename = '{test}-{thread_level}.{file_format}'.format(
                                test=test_identifier['test'],
                                thread_level=thread_level,
                                file_format=command_config.file_format)
                            helpers.save_plot(figure, pathname, filename)
                        if show:
                            figure.show()
                        figure.close()

                except KeyError:
                    LOG.error('unexpected error', exc_info=1)
                    if figure is not None:
                        figure.close()


@cli.command(name='list-build-failures')
@click.pass_obj
@click.option(
    '--human-readable',
    'human_readable',
    is_flag=True,
    help='Print output in a more human-friendly output.')
@click.argument('revision', required=True)
@click.argument('project', required=True)
@click.argument('variant', required=False)
@click.argument('task', required=False)
@click.argument('test', required=False)
def list_build_failures_command(command_config, human_readable, revision, project, variant, task,
                                test):
    # pylint: disable=too-many-arguments, too-many-function-args
    """
    Print list of build failures and their linked change points.

Arguments can be string or patterns, A pattern starts with /.

\b
REVISION, the revision of the change point.
PROJECT, the project name or a regex (like /^sys-perf-3.*/ or /^(sys-perf|performance)$/).
VARIANT, the build variant or a regex.
TASK, the task name or a regex.
TEST, the test name or a regex.
\b
You can use '' in place of VARIANT, TASK, TEST, if you want to match all. See the examples.
\b
Examples:
    $> revision=a1b225bcf0e9791b14649df385b3f3f9710a98ab
\b
    # List all build failures
    $> change-points list-build-failures
\b
    # List all build failures for a revision
    $> change-points list-build-failures $revision
\b
    # List sys-perf build failures for a revision
    $> change-points list-build-failures $revision sys-perf
\b
    # List sys-perf build failures (any revision)
    $> change-points list-build-failures '' sys-perf
\b
    # List build failures matching criteria
    $> change-points list-build-failures $revision sys-perf linux-1-node-replSet
    $> change-points list-build-failures $revision sys-perf '/linux-.-node-replSet/'
\b
    # List all build failures with sys-perf find_limit-useAgg (any revision)
    $> change-points list-build-failures '' sys-perf '' '' find_limit-useAgg
\b
    # List build failures in a more human-friendly format
    $> change-points list-build-failures --human-readable
    $> change-points list-build-failures $revision sys-perf linux-1-node-replSet --human-readable
"""
    query = helpers.process_params(revision, project, variant, task, test, None)
    list_build_failures.list_build_failures(query, human_readable, command_config)


@cli.command(name='failures')
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
