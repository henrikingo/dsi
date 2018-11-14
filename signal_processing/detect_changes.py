"""
Run the QHat algorithm and store results.
"""
import os
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

ARRAY_FIELDS = set(['series', 'revisions', 'orders', 'create_times', 'task_ids', 'version_ids'])
"""
The set of array field keys. These arrays must be equal in size.
"""


class PointsModel(object):
    """
    Model that gathers the point data and runs QHat to find change points.
    """

    # pylint: disable=invalid-name, too-many-instance-attributes
    def __init__(self, mongo_uri, limit=None, pvalue=None, mongo_repo=None, credentials=None):
        # pylint: disable=too-many-arguments
        """
        PointsModel is serializable through pickle. To maintain a consistent stable interface, it
        delegates configuration to __setstate__.
        See methods '__getstate__' and '__setstate__'.

        :param str mongo_uri: The uri to connect to the cluster.
        :param limit: The limit for the number of points to retrieve from the database.
        :type limit: int, None.
        :param pvalue: The pvalue for the QHat algorithm.
        :type pvalue: int, float, None.
        :param mongo_repo: The mongo git location.
        :param credentials: The git credentials.
        """
        self.__setstate__({
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

    def get_points(self, test_identifier):
        """
        Retrieve the documents from the `points` collection in the database for the given test.

        :param dict test_identifier: The project / variant / task / test and thread_level.
        :return: The results from the query to the database as well as some additional information
        extracted from those results.
        :return: The number of points (and thus the length of the lists), the query used to retrieve
        the points and a dict of lists for the metrics for each point (ops/s, revisions, orders,
        create_times, task_ids).
        :rtype: tuple(int, OrderedDict, dict).
        """

        required_fields = {
            'project': 1,
            'revision': 1,
            'variant': 1,
            'task': 1,
            'test': 1,
            'order': 1,
            'create_time': 1,
            'task_id': 1,
            'version_id': 1,
        }

        filter_thread_level = required_fields.copy()
        filter_thread_level['results'] = {
            '$filter': {
                'input': '$results',
                'as': 'result',
                'cond': {
                    '$eq': ['$$result.thread_level', test_identifier['thread_level']]
                }
            }
        }

        query = test_identifier.copy()
        thread_level = query['thread_level']
        del query['thread_level']
        query['results.thread_level'] = thread_level

        grouping = {
            '_id': {
                'project': '$project',
                'variant': '$variant',
                'task': '$task',
                'test': '$test',
                'thread_level': {
                    '$arrayElemAt': ['$results.thread_level', 0]
                }
            },
            'size': {
                '$sum': 1
            },
            'series': {
                '$push': {
                    '$arrayElemAt': ['$results.ops_per_sec', 0]
                }
            },
            'revisions': {
                '$push': '$revision'
            },
            'orders': {
                '$push': '$order'
            },
            'create_times': {
                '$push': '$create_time'
            },
            'task_ids': {
                '$push': '$task_id'
            },
            'version_ids': {
                '$push': '$version_id'
            }
        }

        # filter documents that contain no or empty field values
        required_keys = {'$and': [{key: {'$ne': None}} for key in REQUIRED_KEYS]}

        pipeline = [{'$match': query},
                    {'$match': required_keys},
                    {'$sort': {'order': 1}},
                    {'$project': filter_thread_level}] # yapf: disable
        if self.limit is not None:
            pipeline.append({'$limit': self.limit})
        pipeline.append({'$group': grouping})
        pipeline.append({
            '$project': {
                '_id': 0,
                'project': '$_id.project',
                'variant': '$_id.variant',
                'task': '$_id.task',
                'test': '$_id.test',
                'testname': '$_id.test',
                'thread_level': '$_id.thread_level',
                'size': 1,
                'series': 1,
                'revisions': 1,
                'orders': 1,
                'create_times': 1,
                'task_ids': 1,
                'version_ids': 1
            }
        })

        points = list(self.db.points.aggregate(pipeline))
        results = points[0]
        sizes = {key: len(results[key]) for key in ARRAY_FIELDS}
        if not all(current == sizes.values()[0] for current in sizes.values()):
            raise Exception('All array sizes were not equal: {}'.format(sizes))

        return results

    def compute_change_points(self, test_identifier, weighting):
        """
        Compute the change points for the given test using the QHat algorithm and insert them into
        the `change_points` collection of the database.

        :param dict test_identifier: The project / variant / task / test and thread_level.
        :param float weighting: The weighting for the decay on compute.
        :return: The number of points for the test, the number of change points found by the QHat
        algorithm, and the time taken for this method to run.
        :rtype: tuple(int, int, float).
        See 'QHat.DEFAULT_WEIGHTING' for the recommended default value.
        """
        # pylint: disable=too-many-locals
        thread_level_results = self.get_points(test_identifier)

        change_points = qhat.QHat(
            thread_level_results,
            pvalue=self.pvalue,
            weighting=weighting,
            mongo_repo=self.mongo_repo,
            credentials=self.credentials).change_points
        LOG.debug(
            "compute_change_points starting",
            change_points=len(change_points),
            test_identifier=test_identifier)

        # Poor mans transaction. Upgrade to 4.0?
        # TODO: TIG-1174
        before = list(self.db.change_points.find(test_identifier))

        try:
            requests = [pymongo.DeleteMany(test_identifier)]

            for point in change_points:
                change_point = test_identifier.copy()
                change_point.update(point)
                index = thread_level_results['orders'].index(point['order'])
                change_point['task_id'] = thread_level_results['task_ids'][index]
                change_point['version_id'] = thread_level_results['version_ids'][index]
                requests.append(pymongo.InsertOne(change_point))

            self.db.change_points.bulk_write(requests)

            return thread_level_results['size'], len(change_points)
        except:
            LOG.warn('compute_change_points failed. Attempting to rollback.', exc_info=True)
            requests = [pymongo.DeleteMany(test_identifier)] +\
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
            pool_size = max(1, (multiprocessing.cpu_count() - 1) * 2)
        self.pool_size = pool_size
        self.progressbar = progressbar

    # pylint: disable=too-many-locals
    def run(self):
        """
        Run the analysis to compute any change points with the new data.
        """
        model = PointsModel(
            self.mongo_uri, mongo_repo=self.mongo_repo, credentials=self.credentials)

        test_identifiers = etl_helpers.extract_test_identifiers(self.perf_json)
        LOG.info('loaded tests', test_identifiers=len(test_identifiers))
        LOG.debug('loaded tests', test_identifiers=test_identifiers)
        label = 'detecting changes'

        test_identifiers = [
            thread_identifier
            for test_identifier in test_identifiers
            for thread_identifier in etl_helpers.generate_thread_levels(
                test_identifier, model.db.points)
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
