"""
Run the QHat algorithm and store results.
"""
import os
from collections import OrderedDict, defaultdict
from datetime import datetime
import multiprocessing

import click
import pymongo
import structlog

import etl_helpers
import qhat
import signal_processing.commands.helpers as helpers
import signal_processing.commands.jobs as jobs
from analysis.evergreen import evergreen_client
from bin.common import config, log

LOG = structlog.getLogger(__name__)

DEFAULT_MONGO_REPO = '../src'
"""
The expected mongo repo location for performance or sys-perf.
"""

REQUIRED_KEYS = set(['revision', 'order', 'create_time'])
"""
The set of keys that a valid performance point must in include.
"""


class PointsModel(object):
    """
    Model that gathers the point data and runs QHat to find change points.
    """

    # pylint: disable=invalid-name, too-many-instance-attributes
    def __init__(self,
                 perf_json,
                 mongo_uri,
                 limit=None,
                 pvalue=None,
                 mongo_repo=None,
                 credentials=None):
        # pylint: disable=too-many-arguments
        """
        PointsModel is serializable through pickle. To maintain a consistent stable interface, it
        delegates configuration to __setstate__.
        See methods '__getstate__' and '__setstate__'.

        :param dict perf_json: The raw data json file from Evergreen mapped to a Python dictionary.
        :param str mongo_uri: The uri to connect to the cluster.
        :param limit: The limit for the number of points to retrieve from the database.
        :type limit: int, None.
        :param pvalue: The pvalue for the QHat algorithm.
        :type pvalue: int, float, None.
        :param mongo_repo: The mongo git location.
        :param credentials: The git credentials.
        """
        self.__setstate__({
            'perf_json': perf_json,
            'mongo_uri': mongo_uri,
            'limit': limit,
            'pvalue': pvalue,
            'mongo_repo': mongo_repo,
            'credentials': credentials
        })

    # pylint: disable=attribute-defined-outside-init
    @property
    def db(self):
        """
        Getter for self._db.
        """
        if self._db is None:
            self._db = pymongo.MongoClient(self.mongo_uri).get_database()
        return self._db

    def get_points(self, test):
        """
        Retrieve the documents from the `points` collection in the database for the given test.

        :param str test: The name of the test.
        :return: The results from the query to the database as well as some additional information
        extracted from those results.
        :return: The number of points (and thus the length of the lists), the query used to retrieve
        the points and a dict of lists for the metrics for each point (ops/s, revisions, orders,
        create_times, task_ids).
        :rtype: tuple(int, OrderedDict, dict).
        """

        query = OrderedDict([('project', self.perf_json['project_id']),
                             ('variant', self.perf_json['variant']),
                             ('task', self.perf_json['task_name']),
                             ('test', test)]) #yapf: disable

        projection = {
            'results': 1,
            'revision': 1,
            'order': 1,
            'create_time': 1,
            'task_id': 1,
            '_id': 0
        }

        cursor = self.db.points.find(query, projection).sort([('order', pymongo.ASCENDING)])

        if self.limit is not None:
            cursor.limit(self.limit)

        # The following defaultdicts return new lists for missing keys.
        series = defaultdict(list)
        revisions = defaultdict(list)
        orders = defaultdict(list)
        create_times = defaultdict(list)
        task_ids = defaultdict(list)
        size = 0

        points = {
            'series': series,
            'revisions': revisions,
            'orders': orders,
            'create_times': create_times,
            'task_ids': task_ids
        }

        for point in cursor:
            missing = REQUIRED_KEYS - REQUIRED_KEYS.intersection(point.keys())
            if missing:
                LOG.debug("point missing fields", query=query, point=point, missing=missing)
                continue
            for result in point['results']:
                if 'ops_per_sec' not in result:
                    LOG.debug(
                        "result missing fields",
                        query=query,
                        result=result,
                        missing=['ops_per_sec'])
                    continue
                series[result['thread_level']].append(result['ops_per_sec'])
                revisions[result['thread_level']].append(point['revision'])
                orders[result['thread_level']].append(point['order'])
                create_times[result['thread_level']].append(point['create_time'])
                task_ids[result['thread_level']].append(point['task_id'])
                size += 1
        return size, query, points

    def compute_change_points(self, test, weighting):
        """
        Compute the change points for the given test using the QHat algorithm and insert them into
        the `change_points` collection of the database.

        :param str test: The name of the test.
        :param float weighting: The weighting for the decay on compute.
        :return: The number of points for the test, the number of change points found by the QHat
        algorithm, and the time taken for this method to run.
        :rtype: tuple(int, int, float).
        See 'QHat.DEFAULT_WEIGHTING' for the recommended default value.
        """
        # pylint: disable=too-many-locals
        size_points, query, points = self.get_points(test)

        change_points = {}
        size_change_points = 0
        for thread_level in points['series']:
            change_points[thread_level] = qhat.QHat(
                {
                    'series': points['series'][thread_level],
                    'revisions': points['revisions'][thread_level],
                    'orders': points['orders'][thread_level],
                    'create_times': points['create_times'][thread_level],
                    'testname': test,
                    'thread_level': thread_level
                },
                pvalue=self.pvalue,
                weighting=weighting,
                mongo_repo=self.mongo_repo,
                credentials=self.credentials).change_points
            size_change_points += len(change_points[thread_level])
            LOG.debug(
                "compute_change_points starting",
                change_points=len(change_points[thread_level]),
                testname=test,
                thread_level=thread_level)

        # Poor mans transaction. Upgrade to 4.0?
        # TODO: TIG-1174
        before = list(self.db.change_points.find(query))

        try:
            requests = [pymongo.DeleteMany(query)]

            for thread_level in change_points:
                for point in change_points[thread_level]:
                    change_point = query.copy()
                    change_point.update(point)
                    index = points['orders'][thread_level].index(point['order'])
                    change_point['task_id'] = points['task_ids'][thread_level][index]
                    requests.append(pymongo.InsertOne(change_point))

            self.db.change_points.bulk_write(requests)

            return size_points, size_change_points
        except:
            LOG.warn('compute_change_points failed. Attempting to rollback.', exc_info=True)
            requests = [pymongo.DeleteMany(query)] +\
                       [pymongo.InsertOne(point) for point in before]
            self.db.change_points.bulk_write(requests)
            raise

    def __getstate__(self):
        """
        Get state for pickle support.

        Multiprocessor pickles instances to serialize and deserialize to the sub-processes. But
        pickle cannot handle complex types (like a mongo client). However, these instances can
        be recreated on demand in the instance.

        :return: The pickle state.
        """
        return {
            'perf_json': self.perf_json,
            'mongo_uri': self.mongo_uri,
            'limit': self.limit,
            'pvalue': self.pvalue,
            'mongo_repo': self.mongo_repo,
            'credentials': self.credentials
        }

    def __setstate__(self, state):
        """
        Set state for pickle support.

        :param dict state: The pickled state.
        """
        self.perf_json = state['perf_json']
        self.mongo_uri = state['mongo_uri']
        self._db = None
        self.limit = state['limit']
        self.pvalue = state['pvalue']
        self.mongo_repo = state['mongo_repo']
        self.credentials = state['credentials']


def print_result(job):
    """
    Print a description of the test and the results from running the QHat algorithm on the
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

    # pylint: disable=too-few-public-methods,too-many-arguments
    def __init__(self,
                 perf_json,
                 mongo_uri,
                 weighting,
                 mongo_repo,
                 credentials=None,
                 pool_size=None,
                 progressbar=False):
        """
        :param dict perf_json: The raw data json file from Evergreen mapped to a Python dictionary.
        :param str mongo_uri: The uri to connect to the cluster.
        :param float weighting: The weighting value.
        See 'QHat.DEFAULT_WEIGHTING' for the recommended default value.
        :param str mongo_repo: The mongo repo directory.
        :param dict credentials: The github credentials.
        """
        self.perf_json = perf_json
        self.mongo_uri = mongo_uri
        self.weighting = weighting
        self.mongo_repo = mongo_repo
        self.credentials = credentials
        if pool_size is None:
            pool_size = max(1, multiprocessing.cpu_count() - 1)
        self.pool_size = pool_size
        self.progressbar = progressbar

    # pylint: disable=too-many-locals
    def run(self):
        """
        Run the analysis to compute any change points with the new data.
        """
        model = PointsModel(
            self.perf_json,
            self.mongo_uri,
            mongo_repo=self.mongo_repo,
            credentials=self.credentials)

        test_names = etl_helpers.extract_tests(self.perf_json)
        LOG.info('loaded tests', tasks=len(test_names))
        LOG.debug('loaded tests', test_names=test_names)
        label = 'detecting changes'
        bar_template, show_item = helpers.query_terminal_for_bar()

        project = self.perf_json['project_id']
        variant = self.perf_json['variant']
        task = self.perf_json['task_name']
        job_list = [
            jobs.Job(
                model.compute_change_points,
                arguments=(test_name, self.weighting),
                identifier={
                    'project': project,
                    'variant': variant,
                    'task': task,
                    'test': test_name
                }) for test_name in test_names
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
        weighting=qhat.DEFAULT_WEIGHTING,
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
def main(context, logfile, pool_size, verbose, mongo_repo, progressbar):
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
        task_id, patch, mongo_uri, pool_size, mongo_repo=mongo_repo, progressbar=progressbar)

    jobs.handle_exceptions(context, jobs_with_exceptions, logfile)
