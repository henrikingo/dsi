"""
Test Gesd outlier detection with various parameters.
"""
from __future__ import print_function

import multiprocessing
import os
from collections import namedtuple
from datetime import datetime

import click
import numpy as np
import pymongo
import structlog
from nose.tools import nottest
from scipy.stats import probplot

from bin.common.utils import mkdir_p
from signal_processing.commands import helpers, jobs
from signal_processing.commands.helpers import PORTRAIT_FIGSIZE
from signal_processing.detect_changes import PointsModel
from signal_processing.outliers.detection import run_outlier_detection, print_outliers

from matplotlib.ticker import MaxNLocator

LOG = structlog.getLogger(__name__)

TestGesd = namedtuple('TestGesd', [
    'test_identifier', 'max_outliers', 'significance_level', 'mad', 'standardize', 'use_subseries',
    'visualize', 'save', 'change_point', 'plot_critical'
])


def get_matplotlib():
    """
    Import matplotlib.

    Lazy import of matplotlib.
    :return: matplotlib.pyplot or None
    """
    try:
        import matplotlib.pyplot as plt
        return plt
    # pylint: disable=bare-except
    except:
        return None


def normalize_series(series):
    """ Normalize the range of values in the series from 0 to 1."""
    norm_series = np.array(series, dtype=float) - np.min(series, axis=0)
    norm_series /= np.ptp(norm_series, axis=0)
    return norm_series


def standardize_series(series):
    """ Standardize the range of values to the number of standard deviations from the mean."""
    series = np.array(series, dtype=float)
    standard_series = np.array(series - np.mean(series)) / np.std(series)
    return standard_series


def mask_outliers(series, outliers):
    """ Create an array with outliers masked. """
    mask = np.zeros(len(series), np.bool)
    mask[outliers] = 1
    return np.ma.array(series, mask=mask)


def plot_confirmed_outliers(plt, rows, cols, pos, x_values, series, outliers, suspicious,
                            axis=None):
    """

    Plot Outlier data.

    :param matplotlib.pyplot plt: matplotlib.
    :param int rows: The number of rows in the figure.
    :param int cols: The number of columns in the figure.
    :param int pos: The current plot.
    :param list() x_values: The x axis data.
    :param list() series: The time series data.
    :param list() outliers: The confirmed outliers.
    :param list() suspicious: The suspicious outliers.
    :param matplotlib axis: The axes to plot the data on.
    """
    # pylint: disable=too-many-arguments
    if axis is None:
        pos += 1
        axis = plt.subplot(rows, cols, pos)
    masked_series = mask_outliers(series, outliers)

    axis.xaxis.set_major_locator(MaxNLocator(integer=True))
    axis.yaxis.set_major_locator(MaxNLocator(integer=True))
    axis.plot(x_values, series, 'bo-')
    axis.set_title("Outliers")
    axis.plot(x_values, [np.mean(series)] * len(series), "r--")
    axis.plot(x_values, [np.median(series)] * len(series), "r-")
    axis.plot(x_values, [np.ma.mean(masked_series)] * len(masked_series), "k--")
    axis.plot(x_values, [np.ma.median(masked_series)] * len(series), "k-")
    axis.plot(x_values[outliers], series[outliers], "ro", markersize=20)
    for i, index in enumerate(outliers):
        axis.annotate(
            str(i + 1), (x_values[index], series[index]), (x_values[index] - 1, series[index]))
    if suspicious is not None and suspicious:
        axis.plot(x_values[suspicious], series[suspicious], "k*", markersize=20)
    return pos


def plot_without_confirmed_outliers(plt,
                                    rows,
                                    cols,
                                    pos,
                                    x_values,
                                    series,
                                    outliers,
                                    suspicious,
                                    axis=None):
    """

    Plot Outlier data.

    :param int rows: The number of rows in the figure.
    :param int cols: The number of columns in the figure.
    :param int pos: The current plot.
    :param list() x_values: The x axis data.
    :param list() series: The time series data.
    :param list() outliers: The confirmed outliers.
    :param list() suspicious: The suspicious outliers.
    :param matplotlib axis: The axes to plot the data on.
    """
    # pylint: disable=too-many-arguments
    if axis is None:
        pos += 1
        axis = plt.subplot(rows, cols, pos)
    masked_series = mask_outliers(series, outliers)

    axis.xaxis.set_major_locator(MaxNLocator(integer=True))
    axis.set_title("Outliers Removed")
    axis.plot(x_values, masked_series, 'bo-')
    axis.plot(x_values, [np.ma.mean(masked_series)] * len(masked_series), "r--")
    axis.plot(x_values, [np.ma.median(masked_series)] * len(series), "r-")
    if suspicious is not None and suspicious:
        axis.plot(x_values[suspicious], masked_series[suspicious], "k*", markersize=20)
    return pos


def plot_without_any_outliers(plt,
                              rows,
                              cols,
                              pos,
                              x_values,
                              series,
                              outliers,
                              suspicious,
                              axis=None):
    """

    Plot Outlier data.

    :param int rows: The number of rows in the figure.
    :param int cols: The number of columns in the figure.
    :param int pos: The current plot.
    :param list() x_values: The x axis data.
    :param list() series: The time series data.
    :param list() outliers: The confirmed outliers.
    :param list() suspicious: The suspicious outliers.
    :param matplotlib axis: The axes to plot the data on.
    """
    # pylint: disable=too-many-arguments
    if axis is None:
        pos += 1
        axis = plt.subplot(rows, cols, pos)

    all_masked_series = mask_outliers(series, outliers + suspicious)
    axis.xaxis.set_major_locator(MaxNLocator(integer=True))
    axis.set_title("All Outliers Removed")
    axis.plot(x_values, all_masked_series, 'bo-')
    axis.plot(x_values, [np.ma.mean(all_masked_series)] * len(series), "r--")
    axis.plot(x_values, [np.ma.median(all_masked_series)] * len(series), "r-")
    return pos


@nottest
def plot_test_scores(plt,
                     rows,
                     cols,
                     pos,
                     test_statistics,
                     critical_values,
                     outliers,
                     suspicious,
                     axis=None):
    """
    Plot Outlier data.

    :param int rows: The number of rows in the figure.
    :param int cols: The number of columns in the figure.
    :param int pos: The current plot.
    :param list() test_statistics: The x axis data.
    :param list() critical_values: The time series data.
    :param list() outliers: The confirmed outliers.
    :param list() suspicious: The suspicious outliers.
    :param matplotlib axis: The axes to plot the data on.
    """
    # pylint: disable=too-many-arguments
    if axis is None:
        pos += 1
        axis = plt.subplot(rows, cols, pos)
        axis.xaxis.set_major_locator(MaxNLocator(integer=True))

    all_outliers = outliers + suspicious
    axis.set_title("z scores v critical")
    axis.xaxis.set_ticks(np.arange(len(all_outliers)))
    axis.set_xticklabels([str(i) for i in all_outliers], fontdict=None, minor=False)
    axis.plot(range(len(all_outliers)), test_statistics, 'r-')
    axis.plot(range(len(all_outliers)), np.abs(test_statistics), 'r-')
    axis.plot(range(len(all_outliers)), critical_values, 'k-')
    return pos


def plot_probability(plt, rows, cols, pos, series, title=None, axis=None):
    """
    Plot Outlier data.

    :param int rows: The number of rows in the figure.
    :param int cols: The number of columns in the figure.
    :param int pos: The current plot.
    :param list series: The data to plot.
    :param str title: The sub plot title.
    :param matplotlib axis: The axes to plot the data on.
    """
    # pylint: disable=too-many-arguments
    if axis is None:
        pos += 1
        axis = plt.subplot(rows, cols, pos)
        axis.xaxis.set_major_locator(MaxNLocator(integer=True))

    if title:
        axis.set_title(title)
    axis.xaxis.set_major_locator(MaxNLocator(integer=True))
    probplot(series, plot=axis, rvalue=True)

    return pos


def plot_histogram(plt, rows, cols, pos, series, title=None, axis=None):
    """
    Plot Outlier data.

    :param int rows: The number of rows in the figure.
    :param int cols: The number of columns in the figure.
    :param int pos: The current plot.
    :param list series: The data to plot.
    :param str title: The sub plot title.
    :param matplotlib axis: The axes to plot the data on.
    """
    # pylint: disable=too-many-arguments
    if axis is None:
        pos += 1
        axis = plt.subplot(rows, cols, pos)
        axis.xaxis.set_major_locator(MaxNLocator(integer=True))

    if title:
        axis.set_title(title)
    axis.xaxis.set_major_locator(MaxNLocator(integer=True))
    axis.hist(series)

    return pos


def plot_gesd(test_identifier,
              series,
              outliers,
              suspicious,
              test_statistics,
              critical_values,
              all_z_scores,
              mad,
              full_series,
              start,
              end,
              significance,
              standardize=True,
              plot_critical=False):
    """
    Plot GESD output.

    :param dict() test_identifier: The dict of project / variant / task / test / thread level.
    :param list(float) series: The time series data.
    :param list(int) outliers: The indexes of confirmed outliers.
    :param list(int) suspicious: The indexes of suspicious points.
    :param list(float) test_statistics: The max z score / iteration.
    :param list(float) critical_values: The critical value / iteration.
    :param list(float, float) all_z_scores: A matrix of z scores for each iteration.
    :param bool mad: True if the z score used Medaian Absolute Deviation.
    :param list(dict) full_series: The full time series data.
    :param int start: The start index within the full series.
    :param int end: The end index within the full series.
    :param float significance: The p value used for significance test.
    :param bool standardize: If True then standardize series into the number of standard
    deviations from mean.
    :param bool plot_critical: If True then plot z scores v critical values.
    :return: The figure with the plot.
    """
    # pylint: disable=too-many-locals, too-many-arguments
    LOG.debug(
        'plot gesd',
        test_identifier=test_identifier,
        series=series,
        outliers=outliers,
        suspicious=suspicious,
        test_statistics=test_statistics,
        critical_values=critical_values,
        all_z_scores=all_z_scores,
        mad=mad,
        significance=significance,
        standardize=standardize)

    plt = get_matplotlib()
    if plt is not None:
        font = {'family': 'serif', 'color': 'darkred', 'weight': 'normal', 'size': 16}

        series = np.array(series, dtype=float)
        if standardize:
            series = standardize_series(series)

        x_values = np.arange(len(series))

        plt.figure(figsize=PORTRAIT_FIGSIZE)
        rows, cols, pos = [5, 1, 0]
        if plot_critical:
            rows += 1

        pos = plot_confirmed_outliers(plt, rows, cols, pos, x_values, series, outliers, suspicious)
        pos = plot_without_confirmed_outliers(plt, rows, cols, pos, x_values, series, outliers,
                                              suspicious)
        if plot_critical:
            pos = plot_test_scores(plt, rows, cols, pos, test_statistics, critical_values, outliers,
                                   suspicious)

        pos = plot_probability(plt, rows, cols, pos, series, 'All Data')
        pos = plot_probability(plt, rows, cols, pos,
                               mask_outliers(series, outliers).compressed(), 'Data less outliers')

        pos = plot_histogram(plt, rows, cols, pos, series, title='Data Histogram')

        create_times = full_series['create_times']
        title = """{test_identifier}
Standardize: {standardized}, MAD: {mad}, p={p}
{start_time} - {end_time}""".format(test_identifier=test_identifier,
                                    standardized='on ' if standardize else 'off',
                                    mad='on' if mad else 'off',
                                    p=significance,
                                    start_time=create_times[start][:-4],
                                    end_time=create_times[end][:-4])  # yapf: disable
        plt.suptitle(title, fontdict=font)
    return plt


def get_change_point_range(test_identifier, change_points, series, index=-1):
    """ Calculate the range  of data for a given change point. """
    change_points = list(change_points.find(test_identifier).sort([('order', pymongo.ASCENDING)]))
    LOG.debug('Loaded change points', change_points=change_points)

    if change_points:

        order = change_points[index]['order']
        start = series['orders'].index(order)
        if index == -1:
            end = len(series['orders'])
        else:
            order = change_points[index + 1]['order']
            end = series['orders'].index(order)
    else:
        start = 0
        end = len(series['orders'])

    sub_series = series['series'][start:end]
    return start, end, sub_series


def config_gesd(command, command_config):
    """ Test Gesd Outlier Detection with different parameters. """
    # pylint: disable=too-many-locals
    model = PointsModel(
        command_config.mongo_uri,
        0,
        mongo_repo=command_config.mongo_repo,
        credentials=command_config.credentials)

    full_series = model.get_points(command.test_identifier, 0)
    LOG.debug("Loaded Series", series=full_series)

    start, end, series = get_change_point_range(
        command.test_identifier,
        command_config.change_points,
        full_series,
        index=command.change_point)

    detection_result = run_outlier_detection(full_series, start, end, series,
                                             command.test_identifier, command.max_outliers,
                                             command.mad, command.significance_level)

    if len(detection_result.series) == 1:
        print("\n{identifier} {start} {end}".format(
            identifier=detection_result.identifier,
            start=detection_result.start,
            end=detection_result.end))
        return

    lines = print_outliers(detection_result)

    pathname = os.path.join(command_config.out, command.test_identifier['project'],
                            command.test_identifier['variant'], command.test_identifier['task'],
                            "{:03f}".format(command.significance_level))

    filename_no_ext = '{test}-{thread_level}-{outliers}-{mad}-{p}'.format(
        test=command.test_identifier['test'],
        outliers=detection_result.num_outliers,
        thread_level=command.test_identifier['thread_level'],
        mad='on' if command.mad else 'off',
        p=command.significance_level)

    if command.save:
        filename = '{filename}.{file_format}'.format(filename=filename_no_ext, file_format='txt')
        mkdir_p(pathname)
        with open(os.path.join(pathname, filename), 'w') as stream:
            stream.writelines(lines)

    if command.visualize or command.save:
        if command.use_subseries:
            data = detection_result.series
            indexes = detection_result.gesd_result.suspicious_indexes
        else:
            data = detection_result.full_series['series']
            indexes = detection_result.adjusted_indexes

        figure = plot_gesd(
            detection_result.identifier,
            data,
            indexes[:detection_result.gesd_result.count],
            indexes[detection_result.gesd_result.count:],
            detection_result.gesd_result.test_statistics,
            detection_result.gesd_result.critical_values,
            detection_result.gesd_result.all_z_scores,
            command.mad,
            detection_result.full_series,
            detection_result.start,
            detection_result.end - 1,
            significance=command.significance_level,
            standardize=command.standardize,
            plot_critical=command.plot_critical)
        if figure is not None:
            if command.save:
                filename = '{filename}.{file_format}'.format(
                    filename=filename_no_ext, file_format=command_config.file_format)
                helpers.save_plot(figure, pathname, filename)

            if command.visualize:
                figure.show()
            figure.close()


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
