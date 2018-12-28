"""
Functionality to compute / recompute change points.
"""
import multiprocessing
from datetime import datetime

import click
import structlog

from signal_processing import detect_changes
from signal_processing.commands import helpers as helpers, jobs as jobs

from signal_processing.detect_changes import PointsModel

LOG = structlog.getLogger(__name__)


def compute_change_points(test_identifier, weighting, command_config, min_points=None):
    """
    Compute all the change points for the test identifier.

    :param dict test_identifier: The project, variant, task, test identifier.
    :param float weighting: The weighting on the decay.
    :param CommandConfig command_config: Common configuration.
    :param min_points: The minimum number of points to consider when detecting change points.
    :type min_points: int or None.
    See 'PointsModel' for more information about the limit parameter.
    :return: The number of points and the change points detected.
    :rtype: dict.
    """
    LOG.debug(
        'computing change points', test_identifier=test_identifier, dry_run=command_config.dry_run)

    points_count = None
    change_points = None
    if not command_config.dry_run:
        mongo_repo = command_config.mongo_repo
        credentials = command_config.credentials
        model = PointsModel(
            command_config.mongo_uri, min_points, mongo_repo=mongo_repo, credentials=credentials)
        points_count, change_points = model.compute_change_points(
            test_identifier, weighting=weighting)
        LOG.info(
            "compute",
            test_identifier=test_identifier,
            points_count=points_count,
            change_points=change_points)
    return {'points': points_count, 'change_points': change_points}


@click.command(name='compute')
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
    help='Set the process pool size. The default is the number of cores - 1.')
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
    query = helpers.process_params(project, variant, task, test, thread_level=thread_level)

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
            compute_change_points,
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
