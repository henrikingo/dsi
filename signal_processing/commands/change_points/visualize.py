"""
Command to visualize change points.
*Note : this functionality is provided as is and is liable to change / break.*
"""
import os
from StringIO import StringIO

import click
import structlog

from signal_processing import detect_changes
from signal_processing.change_points import visualize
from signal_processing.commands import helpers

LOG = structlog.getLogger(__name__)


@click.command(name='visualize')
@click.pass_context
@click.option('--progressbar/--no-progressbar', default=True)
@click.option('--show/--no-show', default=True)
@click.option('--save/--no-save', default=False)
@click.option(
    '--qhat/--no-qhat',
    'show_qhat',
    default=False,
    help="If set to true then display the E-Divisive qhat values for the change points.")
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

    query = helpers.process_params(project, variant, task, test, thread_level=thread_level)
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
