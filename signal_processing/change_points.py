#!/usr/bin/env python2.7
"""
Cli wrapper for various change point operations

To get access to the help try the following command:

    $> change-points help
"""
import functools
from multiprocessing import Pool, cpu_count
from os.path import expanduser, exists, isdir
from StringIO import StringIO
from collections import OrderedDict

import click
import structlog

from analysis.evergreen.helpers import get_git_credentials
from bin.common import log
from signal_processing.commands.compare import print_result, plot_test, \
    compare
from signal_processing.commands.compute import compute_change_points
from signal_processing.commands.helpers import process_params, process_excludes, \
    PROCESSED_TYPE_ACKNOWLEDGED, PROCESSED_TYPE_HIDDEN, PROCESSED_TYPES, get_matching_tasks, \
    filter_legacy_tasks, generate_tests, filter_tests, show_label_function, CommandConfiguration, \
    get_bar_template, get_bar_widths, function_adapter
from signal_processing.commands.list import list_change_points
from signal_processing.commands.mark import mark_change_points
from signal_processing.commands.update import update_change_points
from signal_processing.qhat import DEFAULT_WEIGHTING

DB = "perf"
PROCESSED_CHANGE_POINTS = 'processed_change_points'
CHANGE_POINTS = 'change_points'
POINTS = 'points'
BUILD_FAILURES = 'build_failures'

LOG = structlog.getLogger(__name__)

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'], max_content_width=120)


@click.group(context_settings=CONTEXT_SETTINGS, invoke_without_command=True)
@click.option(
    '-d', '--debug', count=True, help='Enable debug output, you can pass multiple -ddddd etc.')
@click.option('-l', '--logfile', default=None, help='The log file to write to, defaults to None.')
@click.option('-o', '--out', default="/tmp", help="The location to save any files in.")
@click.option(
    '-f', '--format', 'file_format', default="png", help='The format to save any files in.')
@click.option(
    '-u',
    '--mongo-uri',
    default='mongodb://localhost:27017/' + DB,
    help='MongoDB connection string. The database name comes from here too.')
@click.option('-q', '--queryable', default=False, help="Print ids as queries")
@click.option('-n', '--dry_run', is_flag=True, default=False, help="Don't actually run anything.")
@click.option(
    '-c', '--compact/--expanded', 'compact', default=True, help='Display objects one / line.')
@click.option('--points', default=POINTS, help="The points collection name.")
@click.option('--change_points', default=CHANGE_POINTS, help='The change points collection name.')
@click.option(
    '--processed_change_points',
    default=PROCESSED_CHANGE_POINTS,
    help='The processed change points collection name.')
@click.option(
    '--build_failures', default=BUILD_FAILURES, help='The build failures collection name.')
@click.option(
    '--style', default=['bmh'], multiple=True, help="""The default matplot lib style to use.""")
@click.option('--token-file', default=None, envvar='DSI_TOKEN_FILE')
@click.option('--mongo-repo', 'mongo_repo', default='~/src', envvar='DSI_MONGO_REPO')
@click.pass_context
def cli(context, debug, logfile, out, file_format, mongo_uri, queryable, dry_run, compact, points,
        change_points, processed_change_points, build_failures, style, token_file, mongo_repo):
    """
For a list of styles see 'style sheets<https://matplotlib.org/users/style_sheets.html>'.
"""
    # pylint: disable=missing-docstring, too-many-arguments, too-many-locals
    log.setup_logging(debug > 0, filename=expanduser(logfile) if logfile else logfile)
    credentials = get_git_credentials(token_file) if token_file else None
    mongo_repo = expanduser(mongo_repo) if mongo_repo else mongo_repo
    mongo_repo = mongo_repo if exists(mongo_repo) and isdir(mongo_repo) else None
    context.obj = CommandConfiguration(debug, out, file_format, mongo_uri, queryable, dry_run,
                                       compact, points, change_points, processed_change_points,
                                       build_failures, style, credentials, mongo_repo)
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
    query = process_params(revision, project, variant, task, test, thread_level)
    mark_change_points(PROCESSED_TYPE_ACKNOWLEDGED, query, process_excludes(exclude_patterns),
                       command_config)


@cli.command(name="hide")
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

    query = process_params(revision, project, variant, task, test, thread_level)
    mark_change_points(PROCESSED_TYPE_HIDDEN, query, process_excludes(exclude_patterns),
                       command_config)


@cli.command(name="update")
@click.pass_obj
@click.option(
    '--exclude',
    'exclude_patterns',
    multiple=True,
    help='Exclude all points matching this pattern. This parameter can be provided ' +
    'multiple times.')
@click.option(
    '--processed_type',
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
@click.option(
    '--exclude',
    'exclude_patterns',
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


@cli.command(name="compare")
@click.pass_obj
@click.option('-m', '--minsize', 'minsizes', default=[20], type=click.INT, multiple=True)
@click.option('-s', '--sig', 'sig_lvl', default=.05)
@click.option('-p', '--padding', default=0, help='append this many repetitions of the last result.')
@click.option('--progressbar/--no-progressbar', default=True)
@click.option('--show/--no-show', default=False)
@click.option('--save/--no-save', default=False)
@click.option('--exclude', 'excludes', multiple=True)
@click.option(
    '--no-older',
    default=30,
    help='exclude tasks that have no points newer than this number of days.')
@click.option('--weighting', 'weighting', default=DEFAULT_WEIGHTING)
@click.argument('project', required=False)
@click.argument('variant', required=False)
@click.argument('task', required=False)
@click.argument('test', required=False)
def compare_command(command_config, minsizes, sig_lvl, padding, progressbar, show, save, excludes,
                    no_older, weighting, project, variant, task, test):
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

    query = process_params(None, project, variant, task, test, None)
    LOG.debug('processed params', query=query)

    matching_tasks = filter_legacy_tasks(get_matching_tasks(points, query, no_older))
    LOG.debug('matched tasks', matching_tasks=matching_tasks)

    exclude_patterns = process_excludes(excludes)
    tests = [
        test_identifier for test_identifier in generate_tests(matching_tasks)
        if not filter_tests(test_identifier['test'], exclude_patterns)
    ]
    LOG.debug('matched tests', tests=tests)

    all_calculations = []
    group_by_task = OrderedDict()
    group_by_test = OrderedDict()

    label = "Compare"

    label_width, bar_width, info_width, bar_padding = get_bar_widths()
    bar_template = get_bar_template(label_width, bar_width, info_width)
    show_label = functools.partial(
        show_label_function,
        label_width=label_width,
        bar_width=bar_width,
        info_width=info_width,
        padding=bar_padding)

    with click.progressbar(tests,
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
                calculations = compare(
                    test_identifier,
                    command_config,
                    sig_lvl=sig_lvl,
                    minsizes=minsizes,
                    padding=padding,
                    weighting=weighting)
                all_calculations.extend(calculations)
                for calculation in calculations:
                    identifier = (project, variant, task_name)
                    if identifier not in group_by_task:
                        group_by_task[identifier] = []
                    group_by_task[identifier].append(calculation)

                identifier = (project, variant, task_name, test_name)
                if identifier not in group_by_test:
                    group_by_test[identifier] = []
                group_by_test[identifier].extend(calculations)
            except KeyError:
                LOG.error("unexpected error", exc_info=1)

    for task_identifier, calculations in group_by_task.items():
        project, variant, task_name = task_identifier
        print "{{ project: '{}', variant: '{}', task: '{}' }}".format(project, variant, task_name)

        for result in calculations:
            print_result(result, command_config)

    import matplotlib.pyplot as plt
    with plt.style.context(command_config.style):
        if not command_config.dry_run and save or show:
            for test_identifier, results in group_by_test.items():
                plot_test(save, show, test_identifier, results, padding, sig_lvl, minsizes,
                          command_config.out, command_config.format)


@cli.command(name="compute")
@click.pass_obj
@click.option(
    '--exclude',
    'excludes',
    multiple=True,
    help="Exclude all points matching this pattern. This parameter can be provided "
    "multiple times.")
@click.option('--progressbar/--no-progressbar', default=True)
@click.option('--weighting', default=.001)
@click.option(
    '--pool-size',
    default=max(cpu_count() - 1, 1),
    help="Set the process pool size. The default is the number of cores -1.")
@click.option(
    '--legacy/--no-legacy', default=False, help="Enable creation of legacy change points.")
@click.argument('project', required=True)
@click.argument('variant', required=False)
@click.argument('task', required=False)
@click.argument('test', required=False)
def compute_command(command_config, excludes, progressbar, weighting, pool_size, legacy, project,
                    variant, task, test):
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
    LOG.debug('starting')
    points = command_config.points
    query = process_params(None, project, variant, task, test, None)

    LOG.debug('finding matching tasks', query=query)
    matching_tasks = get_matching_tasks(points, query)
    if not legacy:
        matching_tasks = filter_legacy_tasks(matching_tasks)
    else:
        matching_tasks = list(matching_tasks)

    LOG.debug('finding matching tests in tasks', matching_tasks=matching_tasks)
    exclude_patterns = process_excludes(excludes)
    tests = list(
        test_identifier for test_identifier in generate_tests(matching_tasks)
        if not filter_tests(test_identifier['test'], exclude_patterns))

    label = "compute"
    label_width, bar_width, info_width, padding = get_bar_widths()
    bar_template = get_bar_template(label_width, bar_width, info_width)
    show_label = functools.partial(
        show_label_function,
        label_width=label_width,
        bar_width=bar_width,
        info_width=info_width,
        padding=padding)

    pool = Pool(processes=pool_size)
    tasks = ((compute_change_points, test_identifier, weighting, command_config)
             for test_identifier in tests)
    task_iterator = pool.imap_unordered(function_adapter, tasks)
    LOG.debug('finding matching tests in tasks', tests=tests)
    with click.progressbar(task_iterator,
                           length=len(tests),
                           label=label,
                           item_show_func=show_label,
                           file=None if progressbar else StringIO(),
                           bar_template=bar_template) as progress: # yapf: disable
        for success, return_value in progress:
            if success:
                test_identifier = return_value
                status = test_identifier['test']
            else:
                exception = return_value
                status = 'Exception: ' + str(exception)
            progress.label = status
            progress.render_progress()

    pool.close()
    pool.join()
