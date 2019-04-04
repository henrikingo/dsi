"""
Command to replay GESD output.
"""
import multiprocessing
from datetime import datetime

import click
import structlog

from signal_processing.change_points.helpers import generate_change_point_ranges
from signal_processing.model.points import PointsModel
from signal_processing.outliers.detection import STANDARD_Z_SCORE, MAD_Z_SCORE
from signal_processing.outliers.replay import ReplayGesdParams, \
    DEFAULT_INTERVAL

from signal_processing.outliers.replay import replay_gesd

from signal_processing.commands import helpers, jobs

LOG = structlog.getLogger(__name__)


# pylint: disable=too-many-locals, too-many-arguments
def _create_jobs(command_config,
                 test_identifiers,
                 change_point_indexes,
                 significance_levels,
                 max_outliers,
                 z_scores,
                 standardize=False,
                 show=True,
                 save=False,
                 all_change_points=False,
                 ticker=False,
                 sigma_range=3.0,
                 interval=DEFAULT_INTERVAL,
                 blit=False):
    """
    Create a list of jobs to dispatch.

    :param CommandConfig command_config: The configuration common to all.
    :param list(int) change_point_indexes: The change point indexes to plot. Python indexing is
    used so [-1] for the last change point. [] implies all change points, and all_change_points
    overrides this array.
    :param list(float) significance_levels: The significance levels to use as part of the
    student's t test.
    :param list(int) max_outliers: The max outliers to find. A value of 0 implies calculate the
    number of outliers based on the time series range data.
    :param list(str) z_scores: The z score calculation algorithm, allowable values are
    STANDARD_Z_SCORE or MAD_Z_SCORE.
    :param bool standardize: If True then the time series data will be standardized.
    :param bool show: If true then the plot will be displayed.
    :param bool save: If true then the plot will be saved to a file.
    :param bool all_change_points: If true then the plot all change points.
    :param bool ticker: If true then calculate the plot x and y limits on the fly.
    :param float sigma_range: The number of standard deviations to display as a range on the plot.
    :param int interval: The delay between frames (in millis).
    :param bool blit: The delay between frames (in millis).
    :see https://en.wikipedia.org/wiki/Standard_score
    :see https://en.wikipedia.org/wiki/Student%27s_t-test
    """

    model = PointsModel(
        command_config.mongo_uri,
        0,
        mongo_repo=command_config.mongo_repo,
        credentials=command_config.credentials)

    if all_change_points:
        change_point_indexes = []

    kwargs = dict(
        standardize=standardize,
        show=show,
        save=save,
        ticker=ticker,
        sigma_range=sigma_range,
        interval=interval,
        blit=blit)

    # yapf: disable
    job_list = [
        jobs.Job(
            replay_gesd,
            arguments=(ReplayGesdParams(
                test_identifier=test_identifier,
                outliers=outliers,
                significance=significance,
                z_score=z_score,
                start_order=start_order,
                end_order=end_order), command_config),
            kwargs=kwargs,
            identifier=test_identifier)
        for test_identifier in test_identifiers
        for start_order, end_order in generate_change_point_ranges(
            test_identifier,
            model,
            change_point_indexes)
        for z_score in z_scores
        for outliers in max_outliers
        for significance in significance_levels
    ]
    return job_list


@click.command(name='replay')
@click.pass_context
@click.argument('project', required=True)
@click.argument('variant', required=False)
@click.argument('task', required=False)
@click.argument('test', required=False)
@click.argument('thread_level', required=False)
@click.option(
    '--exclude',
    'excludes',
    multiple=True,
    help='Exclude all points matching this pattern. This parameter can be provided multiple times.')
@click.option(
    '--progressbar/--no-progressbar', default=True, help='Enable or disable the progressbar.')
@click.option(
    '--pool-size',
    callback=helpers.validate_int_none_options,
    default='None',
    help="""Set the process pool size. If show is True then default is 0 (no sub-processes).
Otherwise the default is the number of cores - 1.""")
@click.option(
    '--significance',
    '-p',
    'significance_levels',
    type=float,
    default=[0.05],
    multiple=True,
    help="""The threshold level for student\'s t-test. Calculated p-values below this value
reject the null hypothesis.""")
@click.option(
    '--max-outliers',
    '-m',
    type=float,
    default=[0.0],
    callback=helpers.validate_outlier_percentages,
    multiple=True,
    help="""The Max outliers as a float percentage. 0 implies use the default (20%). Valid range is
from 0.0 to 1.0. Multiple values are allowed. It is not recommended to use a value > 20 in
production. Values greater than 20% are really only for test and validation purposes.""")
@click.option(
    '--z-score',
    'z_scores',
    type=click.Choice([STANDARD_Z_SCORE, MAD_Z_SCORE]),
    default=[STANDARD_Z_SCORE],
    multiple=True,
    help='Specify the z score type to use. This can be supplied multiple times.')
@click.option(
    '--show/--no-show',
    'show',
    is_flag=True,
    default=True,
    help='Show the replay as it is calculated.')
@click.option(
    '--save/--no-save',
    'save',
    is_flag=True,
    default=False,
    help="""Save the replay, this does not imply show. If save is True and show is False then
multiple processes can be used.""")
@click.option(
    '--standardize/--no-standardize',
    'standardize',
    is_flag=True,
    default=False,
    help="""Standardize the time series data. Convert the values to represent the number of
standard deviations from the mean.""")
@click.option(
    '--change-point',
    'change_point_indexes',
    default=[-1],
    type=int,
    multiple=True,
    help='The change point range (python indexing, -1 being the last).')
@click.option('--all-change-points', is_flag=True, default=False, help='Plot all change points.')
@click.option('--ticker / --no-ticker', is_flag=True, default=False, help='Plot as ticker tape.')
@click.option(
    '--sigma',
    'sigma_range',
    default=3.0,
    help='The number of standard deviations from the mean to show on the graph.')
@click.option(
    '--interval',
    default=DEFAULT_INTERVAL,
    help='The delay between frames in milliseconds. Defaults to 200.')
@click.option(
    '--blit / --no-blit',
    default=False,
    is_flag=True,
    help='Controls whether blitting is used to optimize drawing. Defaults to False.')
# pylint: disable=too-many-locals, too-many-arguments
def replay_command(context, project, variant, task, test, thread_level, excludes, progressbar,
                   pool_size, significance_levels, max_outliers, z_scores, save, show, standardize,
                   change_point_indexes, all_change_points, ticker, sigma_range, interval, blit):
    """
Replay the outlier detection for the test specified by project / variant / task / test and thread
level.

It is intended that the test will be a canary test, but that is not precluded by this command.

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
    # replay outlier and show detection for the last change point range for the test identifier.
    # In this case:
    #     sys-perf project
    #     linux-standalone variant
    #     bestbuy_agg task
    #     canary_client-cpuloop-10x test
    #     1 thread level
    $> outliers replay sys-perf linux-standalone bestbuy_agg canary_client-cpuloop-10x 1
\b
    # Same as the previous command.
    $> outliers replay sys-perf linux-standalone bestbuy_agg canary_client-cpuloop-10x 1 \\
       --z-score standard
\b
    # Same as the previous command but use Median Absolute Deviation for the z score calculation.
    $> outliers replay sys-perf linux-standalone bestbuy_agg canary_client-cpuloop-10x 1 \\
       --z-score mad
\b
    # Same as the previous command but both MAD and standard z score calculations. The replays
    # are generated / shown separately.
    $> outliers replay sys-perf linux-standalone bestbuy_agg canary_client-cpuloop-10x 1 \\
       --z-score mad --z-score standard
\b
    # Same as the original command but scale the time series data to represent the number of
    # standard deviations from the mean.
    $> outliers replay sys-perf linux-standalone bestbuy_agg canary_client-cpuloop-10x 1 \\
       --standardize
\b
    # Same as the original command but replay at with each significance level, these levels are
    # replayed separately.
    $> outliers replay sys-perf linux-standalone bestbuy_agg canary_client-cpuloop-10x 1 \\
       --significance 0.05 --significance 0.1 --significance 0.15
\b
    # Same as the original command but replay with specific max outlier percentages, these are
    # replayed separately.
    $> outliers replay sys-perf linux-standalone bestbuy_agg canary_client-cpuloop-10x 1 \\
       --max-outliers .1 --max-outliers .2
\b
    # Same as the original command but don't render the output visually (there will be output to
    # the console).
    $> outliers replay sys-perf linux-standalone bestbuy_agg canary_client-cpuloop-10x 1 \\
       --no-show
\b
    # Same as the original command but render the output to a file. The output of this command
    # will be run in separate processes. Although the fact that there is only a single job will
    # negate any benefit of multiprocessing.
    $> outliers replay sys-perf linux-standalone bestbuy_agg canary_client-cpuloop-10x 1 \\
       --no-show --save
\b
    # replay outlier detection for all sys perf canary tests at all thread levels. The output will
    # be saved to the file system and will be run in multiple processes.
    $> outliers replay sys-perf '/^linux/' '' '/^(canary|fio|NetworkBandwidth)/ \\
       --no-show --save
"""
    LOG.debug(
        'replay command',
        project=project,
        variant=variant,
        task=task,
        test=test,
        thread_level=thread_level,
        excludes=excludes,
        progressbar=progressbar,
        pool_size=pool_size,
        significance_levels=significance_levels,
        max_outliers=max_outliers,
        z_scores=z_scores,
        save=save,
        show=show,
        standardize=standardize,
        change_point_indexes=change_point_indexes,
        all_change_points=all_change_points,
        ticker=ticker,
        sigma_range=sigma_range,
        interval=interval,
        blit=blit)

    if pool_size is None and show:
        pool_size = 0
    if pool_size is None:
        pool_size = max(multiprocessing.cpu_count() - 1, 1)

    command_config = context.obj
    points = command_config.points
    query = helpers.process_params(project, variant, task, test, thread_level=thread_level)

    LOG.debug('finding matching tasks', query=query)
    matching_tasks = helpers.get_matching_tasks(points, query)
    matching_tasks = list(helpers.filter_legacy_tasks(matching_tasks))

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

    label = 'replay'

    start_time = datetime.utcnow()
    LOG.debug('finding matching tests in tasks', tests=tests)
    # It is useful for profiling (and testing) to be able to run in a single process
    job_list = _create_jobs(
        command_config,
        test_identifiers,
        change_point_indexes,
        significance_levels,
        max_outliers,
        z_scores,
        standardize=standardize,
        show=show,
        save=save,
        all_change_points=all_change_points,
        ticker=ticker,
        sigma_range=sigma_range,
        interval=interval)

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

    LOG.debug("replay complete", duration=str(datetime.utcnow() - start_time))
    jobs.handle_exceptions(context, jobs_with_exceptions, command_config.log_file)
