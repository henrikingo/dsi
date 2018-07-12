"""
Run the QHat algorithm and store results.
"""
import logging
import time
from collections import OrderedDict

import pymongo

import etl_helpers
from qhat import QHat
from analysis.evergreen import evergreen_client
from bin.common import config
from bin.common import log

LOG = logging.getLogger(__name__)


class PointsModel(object):
    """
    Model that gathers the point data and runs QHat to find change points.
    """

    # pylint: disable=invalid-name

    def __init__(self, perf_json, mongo_uri, limit=None, pvalue=None):
        """
        :param dict perf_json: The raw data json file from Evergreen mapped to a Python dictionary.
        :param str mongo_uri: The uri to connect to the cluster.
        :param limit: The limit for the number of points to retrieve from the database.
        :type limit: int, None.
        :param pvalue: The pvalue for the QHat algorithm.
        :type pvalue: int, float, None.
        """
        # pylint: disable=too-many-arguments
        self.perf_json = perf_json
        self.mongo_uri = mongo_uri
        self._db = None
        self.limit = limit
        self.pvalue = pvalue

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
            for result in point['results']:
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

    def compute_change_points(self, test):
        """
        Compute the change points for the given test using the QHat algorithm and insert them into
        the `change_points` collection of the database.

        :param str test: The name of the test.
        :return: The number of points for the test, the number of change points found by the QHat
        algorithm, and the time taken for this method to run.
        :rtype: tuple(int, int, float).
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
                pvalue=self.pvalue).change_points
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


class DetectChangesDriver(object):
    """
    An entrypoint for detecting change points.
    """

    # pylint: disable=too-few-public-methods

    def __init__(self, perf_json, mongo_uri):
        """
        :param dict perf_json: The raw data json file from Evergreen mapped to a Python dictionary.
        :param str mongo_uri: The uri to connect to the cluster.
        """
        self.perf_json = perf_json
        self.mongo_uri = mongo_uri

    def run(self):
        """
        Run the analysis to compute any change points with the new data.
        """
        model = PointsModel(self.perf_json, self.mongo_uri)
        for test in etl_helpers.extract_tests(self.perf_json):
            many_points, many_change_points, duration = model.compute_change_points(test)
            self._print_result(many_points, many_change_points, duration, test)

    def _print_result(self, many_points, many_change_points, duration, test):
        """
        Print a description of the test and the results from running the QHat algorithm on the
        points for that test.

        :param int many_points: The number of points for the given test.
        :param int many_change_points: The number of change points for the given test.
        :param float duration: The time it took for PointsModel.compute_change_points to run.
        :param str test: The name of the test.
        """
        descriptor = etl_helpers.create_descriptor(self.perf_json, test).ljust(120)
        print("{0}: {1:1} -> {2:2} {3:3,}ms".format(descriptor, many_points, many_change_points,
                                                    duration))


def detect_changes():
    """
    Setup and run the detect changes algorithm.
    """
    log.setup_logging(True, None)
    evg_client = evergreen_client.Client()
    conf = config.ConfigDict('analysis')
    conf.load()
    perf_json = evg_client.query_perf_results(conf['runtime']['task_id'])
    mongo_uri = conf['analysis']['mongo_uri']
    if not conf['runtime'].get('is_patch', False):
        etl_helpers.load(perf_json, mongo_uri)
    changes_driver = DetectChangesDriver(perf_json, mongo_uri)
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
