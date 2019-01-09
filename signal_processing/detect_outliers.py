"""
Run the outlier detection algorithm and display results.
"""
from datetime import datetime
import multiprocessing

import click
import pymongo
import structlog

import etl_helpers
import signal_processing.change_points_cli as change_points_cli
import signal_processing.commands.helpers as helpers
import signal_processing.commands.jobs as jobs
import signal_processing.detect_changes as detect_changes
import signal_processing.outliers.detection as detection
from analysis.evergreen import evergreen_client
from bin.common import config, log

LOG = structlog.getLogger(__name__)


def print_result(job):
    """
    Print a description of the test and the results from running the QHat algorithm on the
    points for that test.

    :param Job job: The job instance.
    """
    if job.exception is None:
        detection_result = job.result
        detection.print_outliers(detection_result)
    else:
        exception = job.exception
        descriptor = etl_helpers.create_descriptor(job.identifier).ljust(120)
        print "{0}: error: {1:1}".format(descriptor, str(exception))


class DetectOutliersDriver(object):
    """
    An entry point for detecting outliers.
    """

    # pylint: disable=too-few-public-methods,too-many-arguments, too-many-instance-attributes
    def __init__(self,
                 perf_json,
                 mongo_uri,
                 max_outliers,
                 mad,
                 significance_level,
                 pool_size=None,
                 progressbar=False):
        """
        :param dict perf_json: The raw data json file from Evergreen mapped to a Python dictionary.
        :param str mongo_uri: The uri to connect to the cluster.
        :param int max_outliers: The max outliers input value for the GESD algorithm.
        :param bool mad: Whether to use Median Absolute Deviation in the GESD algorithm.
        :param float significance_level: The significance level input value for the GESD algorithm.
        :param int pool_size: The size of the process pool size.
        :param bool progressbar: Whether to show a progress bar.
        """
        self.perf_json = perf_json
        self.mongo_uri = mongo_uri

        self.max_outliers = max_outliers
        self.mad = mad
        self.significance_level = significance_level

        if pool_size is None:
            pool_size = max(1, (multiprocessing.cpu_count() - 1) * 2)
        self.pool_size = pool_size
        self.progressbar = progressbar

    # pylint: disable=too-many-locals
    def run(self):
        """
        Run the analysis to compute any change points with the new data.
        """
        model = detect_changes.PointsModel(self.mongo_uri)

        test_identifiers = helpers.extract_test_identifiers(self.perf_json)
        LOG.info('loaded tests', test_identifiers=len(test_identifiers))
        LOG.debug('loaded tests', test_identifiers=test_identifiers)
        label = 'detecting outliers'

        test_identifiers = [
            thread_identifier
            for test_identifier in test_identifiers for thread_identifier in
            helpers.generate_thread_levels(test_identifier, model.db.points)
        ]

        bar_template, show_item = helpers.query_terminal_for_bar()

        order = self.perf_json['order']

        job_list = [
            jobs.Job(
                _get_data_and_run_detection,
                arguments=(model, test_identifier, order, self.max_outliers, self.mad,
                           self.significance_level),
                identifier=test_identifier) for test_identifier in test_identifiers
        ]
        start = datetime.now()
        completed_jobs = jobs.process_jobs(
            job_list, self.pool_size, label, self.progressbar, bar_template, show_item, key='test')
        jobs_with_exceptions = [job for job in completed_jobs if job.exception is not None]

        for job in completed_jobs:
            print_result(job)

        duration = (datetime.now() - start).total_seconds()
        LOG.debug("Detect outliers complete", duration=duration, pool_size=self.pool_size)
        print "Detect outliers complete duration={} over {} processes.".format(
            duration, self.pool_size)

        return jobs_with_exceptions


def get_change_point_range(points_model, test_identifier, full_series, order):
    """Calculate the change point range for a given revision (order)."""
    change_points_col = points_model.db.get_collection(change_points_cli.CHANGE_POINTS)
    change_points = list(
        change_points_col.find(test_identifier).sort([('order', pymongo.DESCENDING)]))

    if change_points:

        start_change_point = None
        start_change_point_index = None
        for i, change_point in enumerate(change_points):
            if change_point['order'] <= order:
                start_change_point = change_point
                start_change_point_index = i
                break

        if start_change_point is not None:
            start = full_series['orders'].index(start_change_point['order'])
            if start_change_point_index == 0:
                # The start change point is the last point.
                end = len(full_series['orders'])
            else:
                end_change_point = change_points[start_change_point_index - 1]
                end = full_series['orders'].index(end_change_point['order'])
        else:
            # order precedes all the change points, returning range before first change point.
            start = 0
            end = full_series['orders'].index(change_points[-1]['order'])

    else:
        start = 0
        end = len(full_series['orders'])

    series = full_series['series'][start:end]
    return start, end, series


# pylint: disable=too-many-arguments
def _get_data_and_run_detection(points_model, test_identifier, order, max_outliers, mad,
                                significance_level):
    """
    Retrieve the time series data and run the outliers detection algorithm.
    """
    full_series = points_model.get_points(test_identifier, 0)
    start, end, series = get_change_point_range(points_model, test_identifier, full_series, order)

    return detection.run_outlier_detection(full_series, start, end, series, test_identifier,
                                           max_outliers, mad, significance_level)


def detect_outliers(task_id,
                    mongo_uri,
                    max_outliers,
                    mad,
                    significance_level,
                    pool_size,
                    progressbar=False):
    """
    Setup and run the detect outliers algorithm.
    """
    evg_client = evergreen_client.Client()
    perf_json = evg_client.query_perf_results(task_id)

    outliers_driver = DetectOutliersDriver(
        perf_json,
        mongo_uri,
        max_outliers,
        mad,
        significance_level,
        pool_size=pool_size,
        progressbar=progressbar)
    return outliers_driver.run()


@click.command()
@click.pass_context
@click.option(
    '--max_outliers',
    type=int,
    default=0,
    help='The max number of outliers number to use in the GESD algorithm.')
@click.option(
    '--mad/--no-mad', 'mad', is_flag=True, default=False, help='Use Median Absolute Deviation')
@click.option(
    '--significance',
    '-p',
    'significance_level',
    type=float,
    default=0.05,
    help='Significance level')
@click.option('-l', '--logfile', default='detect_outliers.log', help='The log file location.')
@click.option(
    '--pool-size', default=None, help='The multiprocessor pool size. None => num(cpus) -1.')
@click.option('-v', 'verbose', count=True, help='Control the verbosity.')
@click.option('--progressbar/--no-progressbar', default=False)
def main(context, max_outliers, mad, significance_level, logfile, pool_size, verbose, progressbar):
    """
    Main function.
    """
    log.setup_logging(True if verbose > 0 else False, filename=logfile)
    conf = config.ConfigDict('analysis')
    conf.load()

    task_id = conf['runtime']['task_id']
    mongo_uri = conf['analysis']['mongo_uri']

    if pool_size is not None:
        pool_size = int(pool_size)

    jobs_with_exceptions = detect_outliers(
        task_id,
        mongo_uri,
        max_outliers,
        mad,
        significance_level,
        pool_size,
        progressbar=progressbar)

    jobs.handle_exceptions(context, jobs_with_exceptions, logfile)
