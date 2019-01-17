"""
Command to compare R v Py change point generation.
"""
from StringIO import StringIO
from collections import OrderedDict

import click
import structlog

import signal_processing.change_points.qhat
import signal_processing.change_points.range_finder
import signal_processing.change_points.weights
from signal_processing import detect_changes
from signal_processing.change_points import compare, qhat
from signal_processing.commands import helpers

LOG = structlog.getLogger(__name__)


@click.command(name='compare')
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
@click.option(
    '--weighting', 'weighting', default=signal_processing.change_points.weights.DEFAULT_WEIGHTING)
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

    query = helpers.process_params(project, variant, task, test)
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
