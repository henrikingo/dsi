"""
Run the E-Divisive algorithm and store results.
"""
import multiprocessing
import os
from datetime import datetime

import click
import structlog

import etl_helpers
from signal_processing.model.points import PointsModel
from signal_processing.change_points import weights
import signal_processing.commands.helpers as helpers
import signal_processing.commands.jobs as jobs
from analysis.evergreen import evergreen_client
from bin.common import config, log

LOG = structlog.getLogger(__name__)

DEFAULT_MIN_SIZE = 500
"""
The default minimum number of points to use when detecting change points. The code attempts to
find the change point nearest min size.
"""

DEFAULT_MONGO_REPO = '../src'
"""
The expected mongo repo location for performance or sys-perf.
"""


def print_result(job):
    """
    Print a description of the test and the results from running the E-Divisive algorithm on the
    points for that test.

    :param Job job: The job instance.
    """
    if job.exception is None:
        many_points, many_change_points = job.result
        descriptor = etl_helpers.create_descriptor(job.identifier).ljust(120)
        print("{0}: {1:1} -> {2:2} {3:3,}ms".format(descriptor, many_points, many_change_points,
                                                    job.duration))
    else:
        exception = job.exception
        descriptor = etl_helpers.create_descriptor(job.identifier).ljust(120)
        print "{0}: error: {1:1}".format(descriptor, str(exception))


class DetectChangesDriver(object):
    """
    An entry point for detecting change points.
    """

    # pylint: disable=too-few-public-methods,too-many-arguments, too-many-instance-attributes
    def __init__(self,
                 perf_json,
                 mongo_uri,
                 weighting,
                 mongo_repo,
                 min_points=None,
                 credentials=None,
                 pool_size=None,
                 progressbar=False):
        """
        :param dict perf_json: The raw data json file from Evergreen mapped to a Python dictionary.
        :param str mongo_uri: The uri to connect to the cluster.
        :param min_points: The minimum number of points to consider when detect change points.
        None implies no minimum.
        :type min_points: int or None.
        See 'PointsModel' for more information about the min_points parameter.
        :param float weighting: The weighting value.
        See 'weights.DEFAULT_WEIGHTING' for the recommended default value.
        :param str mongo_repo: The mongo repo directory.
        :param dict credentials: The github credentials.
        """
        self.perf_json = perf_json
        self.mongo_uri = mongo_uri
        self.min_points = min_points
        self.weighting = weighting
        self.mongo_repo = mongo_repo
        self.credentials = credentials
        if pool_size is None:
            pool_size = max(1, (multiprocessing.cpu_count() - 1) * 2)
        self.pool_size = pool_size
        self.progressbar = progressbar

    # pylint: disable=too-many-locals
    def run(self):
        """
        Run the analysis to compute any change points with the new data.
        """
        model = PointsModel(
            self.mongo_uri,
            self.min_points,
            mongo_repo=self.mongo_repo,
            credentials=self.credentials)

        test_identifiers = helpers.extract_test_identifiers(self.perf_json)
        LOG.info('loaded tests', test_identifiers=len(test_identifiers))
        LOG.debug('loaded tests', test_identifiers=test_identifiers)
        label = 'detecting changes'

        test_identifiers = [
            thread_identifier
            for test_identifier in test_identifiers for thread_identifier in
            helpers.generate_thread_levels(test_identifier, model.db.points)
        ]

        bar_template, show_item = helpers.query_terminal_for_bar()

        job_list = [
            jobs.Job(
                model.compute_change_points,
                arguments=(test_identifier, self.weighting),
                identifier=test_identifier) for test_identifier in test_identifiers
        ]
        start = datetime.now()
        completed_jobs = jobs.process_jobs(
            job_list, self.pool_size, label, self.progressbar, bar_template, show_item, key='test')
        jobs_with_exceptions = [job for job in completed_jobs if job.exception is not None]

        for job in completed_jobs:
            print_result(job)

        duration = (datetime.now() - start).total_seconds()
        LOG.debug("Detect changes complete", duration=duration, pool_size=self.pool_size)
        print "Detect changes complete duration={} over {} processes.".format(
            duration, self.pool_size)

        return jobs_with_exceptions


# pylint: disable=too-many-arguments
def detect_changes(task_id,
                   patch,
                   mongo_uri,
                   min_points,
                   pool_size,
                   mongo_repo=DEFAULT_MONGO_REPO,
                   progressbar=False):
    """
    Setup and run the detect changes algorithm.
    """
    # Send the logging output into detect_changes.log, this needs to be copied into the
    # reports directory later.
    evg_client = evergreen_client.Client()
    perf_json = evg_client.query_perf_results(task_id)
    if not patch:
        etl_helpers.load(perf_json, mongo_uri)
    # TODO : we probably want some way of passing a weighting in going forward. PERF-1588.
    changes_driver = DetectChangesDriver(
        perf_json,
        mongo_uri,
        min_points=min_points,
        weighting=weights.DEFAULT_WEIGHTING,
        mongo_repo=mongo_repo,
        pool_size=pool_size,
        progressbar=progressbar)
    return changes_driver.run()


@click.command()
@click.pass_context
@click.option('-l', '--logfile', default='detect_changes.log', help='The log file location.')
@click.option(
    '--pool-size', default=None, help='The multiprocessor pool size. None => num(cpus) -1.')
@click.option('-v', 'verbose', count=True, help='Control the verbosity.')
@click.option(
    '--mongo-repo',
    'mongo_repo',
    default=DEFAULT_MONGO_REPO,
    help='The location for the mongo repo. This location is used to get the git revisions.')
@click.option('--progressbar/--no-progressbar', default=False)
@click.option(
    '--minimum',
    callback=helpers.validate_int_none_options,
    default=DEFAULT_MIN_SIZE,
    help='The minimum number of points to process. None or zero for all points.')
def main(context, logfile, pool_size, verbose, mongo_repo, progressbar, minimum):
    """
    Main function.

    PERF-1519: While signal processing based analysis is in development, and not yet the official
    truth wrt pass/fail, we want to always exit cleanly.
    TIG-1065: Capture numpy errors and warnings to logs.
    """
    # pylint: disable=broad-except
    log.setup_logging(True if verbose > 0 else False, filename=logfile)
    conf = config.ConfigDict('analysis')
    conf.load()

    task_id = conf['runtime']['task_id']
    patch = conf['runtime'].get('is_patch', False)
    mongo_uri = conf['analysis']['mongo_uri']

    if pool_size is not None:
        pool_size = int(pool_size)

    mongo_repo = os.path.expanduser(mongo_repo)
    jobs_with_exceptions = detect_changes(
        task_id,
        patch,
        mongo_uri,
        minimum,
        pool_size,
        mongo_repo=mongo_repo,
        progressbar=progressbar)

    jobs.handle_exceptions(context, jobs_with_exceptions, logfile)
