"""
Test Gesd outlier detection with various parameters.
"""
from __future__ import print_function

import multiprocessing
from datetime import datetime

import click
import structlog
from signal_processing.commands import helpers, jobs
from signal_processing.outliers.config import config_gesd, TestGesd

LOG = structlog.getLogger(__name__)


@click.command(name='config')
@click.pass_context
@click.argument('project', required=True)
@click.argument('variant', required=False)
@click.argument('task', required=False)
@click.argument('test', required=False)
@click.argument('thread_level', required=False)
@click.option(
    '--significance',
    '-p',
    'significance_levels',
    type=float,
    default=[0.05],
    multiple=True,
    help='Significance level test.')
@click.option(
    '--max-outliers',
    '-m',
    'max_outliers',
    type=int,
    default=[0],
    multiple=True,
    help='Max outliers.')
@click.option(
    '--mad/--no-mad', 'mad', is_flag=True, default=False, help='Use Median Absolute Deviation.')
@click.option(
    '--visualize/--no-visualize', 'visualize', is_flag=True, default=False, help='Plot the series.')
@click.option(
    '--save/--no-save',
    'save',
    is_flag=True,
    default=False,
    help='Save the plot, does not visualize.')
@click.option(
    '--subseries/--series',
    'use_subseries',
    is_flag=True,
    default=True,
    help='Use --series to plot the full time series data.')
@click.option(
    '--standardize/--no-standardize',
    'standardize',
    is_flag=True,
    default=False,
    help='Standardize the time series data.')
@click.option(
    '--pool-size',
    default=max(multiprocessing.cpu_count() - 1, 1),
    help='Set the process pool size. The default is the number of cores - 1.')
@click.option(
    '--change-point',
    default=-1,
    help='The change point range (python indexing, -1 being the last).')
@click.option(
    '--plot-critical', is_flag=True, default=False, help='Plot z score c critical values.')
def config_command(context, project, variant, task, test, thread_level, significance_levels,
                   max_outliers, mad, visualize, save, use_subseries, standardize, pool_size,
                   change_point, plot_critical):
    """ Test the GESD algorithm with various parameters. """
    # pylint: disable=too-many-locals, too-many-arguments
    LOG.debug(
        'test command starting',
        project=project,
        variant=variant,
        task=task,
        test=test,
        thread_level=thread_level,
        significance=significance_levels,
        max_outliers=max_outliers,
        mad=mad,
        change_point=change_point,
        plot_critical=plot_critical)

    command_config = context.obj

    query = helpers.process_params(project, variant, task, test, thread_level=thread_level)
    points = command_config.points

    LOG.debug('finding matching tasks', query=query)
    matching_tasks = helpers.get_matching_tasks(points, query)
    matching_tasks = helpers.filter_legacy_tasks(matching_tasks)

    LOG.debug('finding matching tests in tasks', matching_tasks=matching_tasks)
    tests = list(test_identifier for test_identifier in helpers.generate_tests(matching_tasks))

    test_identifiers = [
        thread_identifier
        for test_identifier in tests for thread_identifier in helpers.generate_thread_levels(
            test_identifier, command_config.points, thread_level=query.get('thread_level', None))
    ]

    label = 'test'
    progressbar = visualize or save

    start_time = datetime.utcnow()

    job_list = [
        jobs.Job(
            config_gesd,
            arguments=(TestGesd(
                test_identifier=test_identifier,
                max_outliers=outliers,
                significance_level=significance,
                mad=mad,
                standardize=standardize,
                use_subseries=use_subseries,
                visualize=visualize,
                save=save,
                change_point=change_point,
                plot_critical=plot_critical), command_config),
            identifier=test_identifier)
        for significance in significance_levels for outliers in max_outliers
        for test_identifier in test_identifiers
    ]

    bar_template, show_item = helpers.query_terminal_for_bar()
    completed_jobs = jobs.process_jobs(
        job_list,
        pool_size=0 if visualize else pool_size,
        label=label,
        progressbar=progressbar,
        bar_template=bar_template,
        show_item=show_item,
        key='test')
    jobs_with_exceptions = [job for job in completed_jobs if job.exception is not None]

    LOG.info("computed change points", duration=str(datetime.utcnow() - start_time))
    jobs.handle_exceptions(context, jobs_with_exceptions, command_config.log_file)
