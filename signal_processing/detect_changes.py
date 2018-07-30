"""
Run the QHat algorithm and store results.
"""
from datetime import datetime
from multiprocessing import Pool, cpu_count
from os.path import expanduser
import time
from collections import OrderedDict

import pymongo
import structlog

import etl_helpers
from qhat import QHat, DEFAULT_WEIGHTING
from analysis.evergreen import evergreen_client
from bin.common import config
from bin.common import log

LOG = structlog.getLogger(__name__)

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
        :return: A list of the maximum operations per second of each point, a list of the revision
        of each point, the query used to retrieve the points, and the number of points returned by
        the query.
        :rtype: tuple(list(float), list(str), OrderedDict, int).
        """

        query = OrderedDict([('project', self.perf_json['project_id']),
                             ('variant', self.perf_json['variant']),
                             ('task', self.perf_json['task_name']),
                             ('test', test)]) #yapf: disable

        projection = {'results': 1, 'revision': 1, 'order': 1, 'create_time': 1, '_id': 0}

        cursor = self.db.points.find(query, projection).sort([('order', pymongo.ASCENDING)])

        if self.limit is not None:
            cursor.limit(self.limit)

        series = {}
        revisions = {}
        orders = {}
        create_times = {}
        many_points = 0

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
                if result['thread_level'] in series:
                    series[result['thread_level']].append(result['ops_per_sec'])
                    revisions[result['thread_level']].append(point['revision'])
                    orders[result['thread_level']].append(point['order'])
                    create_times[result['thread_level']].append(point['create_time'])
                else:
                    series[result['thread_level']] = [result['ops_per_sec']]
                    revisions[result['thread_level']] = [point['revision']]
                    orders[result['thread_level']] = [point['order']]
                    create_times[result['thread_level']] = [point['create_time']]
                many_points += 1

        return series, revisions, orders, query, create_times, many_points

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
        started_at = int(round(time.time() * 1000))

        series, revisions, orders, query, create_times, many_points = self.get_points(test)

        change_points = {}
        many_change_points = 0
        for thread_level in series:
            change_points[thread_level] = QHat(
                {
                    'series': series[thread_level],
                    'revisions': revisions[thread_level],
                    'orders': orders[thread_level],
                    'create_times': create_times[thread_level],
                    'testname': test,
                    'thread_level': thread_level
                },
                pvalue=self.pvalue,
                weighting=weighting,
                mongo_repo=self.mongo_repo,
                credentials=self.credentials).change_points
            many_change_points += len(change_points[thread_level])

        # TODO: Revisit implementation of insert.
        bulk = self.db.change_points.initialize_ordered_bulk_op()
        bulk.find(query).remove()

        for thread_level in change_points:
            for point in change_points[thread_level]:
                change_point = query.copy()
                change_point.update(point)
                bulk.insert(change_point)

        bulk.execute()

        ended_at = int(round(time.time() * 1000))
        return many_points, many_change_points, (ended_at - started_at)

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


def method_adapter(model, test, weighting):
    """
    Multiprocessor doesn't like method references so creating an adapter to handle calling the
    method and return the required types.

    :param PointsModel model: The points model reference.
    :param str test: The test name.
    :param float weighting: The weighting value for the computations.
    :param str test: The name of the test.
    :return: A bool status followed by the return value of method or the exception thrown.
    :rtype: bool, object.
    """
    try:
        many_points, many_change_points, duration = model.compute_change_points(test, weighting)
        return True, model, test, many_points, many_change_points, duration
    except Exception as e:  # pylint: disable=broad-except
        LOG.warn("error in method call", function=model.compute_change_points, exc_info=1)
        return False, e, model, test


def print_result(args):
    """
    Print a description of the test and the results from running the QHat algorithm on the
    points for that test.

    :param list args: The arguments to the function. These comprise of model, many_points,
    many_change_points, duration and test.
    """
    status = args[0]
    if status:
        _, model, test, many_points, many_change_points, duration = args
        descriptor = etl_helpers.create_descriptor(model.perf_json, test).ljust(120)
        print("{0}: {1:1} -> {2:2} {3:3,}ms".format(descriptor, many_points, many_change_points,
                                                    duration))
        LOG.debug(
            "compute_change_points",
            test_identifier=descriptor,
            count_points=many_points,
            count_change_points=many_change_points,
            duration=duration)
    else:
        _, exception, model, test = args
        descriptor = etl_helpers.create_descriptor(model.perf_json, test).ljust(120)
        print "{0}: error: {1:1}".format(descriptor, str(exception))
        LOG.debug(
            "compute_change_points failed", test_identifier=descriptor, exception=str(exception))


class DetectChangesDriver(object):
    """
    An entrypoint for detecting change points.
    """

    # pylint: disable=too-few-public-methods,too-many-arguments
    def __init__(self, perf_json, mongo_uri, weighting, mongo_repo, credentials=None):
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

    def run(self):
        """
        Run the analysis to compute any change points with the new data.
        """
        model = PointsModel(
            self.perf_json,
            self.mongo_uri,
            mongo_repo=self.mongo_repo,
            credentials=self.credentials)

        start = datetime.now()
        pool_size = max(1, cpu_count() - 1)
        pool = Pool(pool_size)
        for test in etl_helpers.extract_tests(self.perf_json):
            pool.apply_async(
                method_adapter, args=(model, test, self.weighting), callback=print_result)
        pool.close()
        pool.join()
        duration = (datetime.now() - start).total_seconds()
        LOG.debug("Detect changes complete", duration=duration, pool_size=pool_size)
        print "Detect changes complete duration={} over {} processes.".format(duration, pool_size)


def detect_changes():
    """
    Setup and run the detect changes algorithm.
    """
    # send the logging output into detect_changes.log, this needs to be copied into the
    # reports directory later.
    log.setup_logging(True, 'detect_changes.log')
    evg_client = evergreen_client.Client()
    conf = config.ConfigDict('analysis')
    conf.load()
    perf_json = evg_client.query_perf_results(conf['runtime']['task_id'])
    mongo_uri = conf['analysis']['mongo_uri']
    if not conf['runtime'].get('is_patch', False):
        etl_helpers.load(perf_json, mongo_uri)
    # TODO : we probably want some way of passing a weighting in going forward. PERF-1588.
    changes_driver = DetectChangesDriver(
        perf_json, mongo_uri, weighting=DEFAULT_WEIGHTING, mongo_repo=expanduser('~/src'))
    changes_driver.run()


def main():
    """
    Main function.

    PERF-1519: While signal processing based analysis is in development, and not yet the official
    truth wrt pass/fail, we want to always exit cleanly.
    """
    # pylint: disable=broad-except
    try:
        detect_changes()
    except Exception:
        # Note: If setup_logging() failed, this will just print:
        #     No handlers could be found for logger "signal_processing.detect_changes"
        LOG.error("detect_changes() exited with an exception. Will print it now...", exc_info=1)
        LOG.error("Will now make a clean exit, so that we don't cause Evergreen task to abort.")
    return 0
