import copy
import json
import pymongo
import time
from collections import OrderedDict
from pymongo import MongoClient

import bin.common.log as log
import analysis.evergreen.evergreen_client as evergreen_client
from qhat import QHat
from bin.common.config import ConfigDict


def _upload_json(perf_json, mongo_uri, database):
    """
    Take the data from perf_json, create documents and upload them to the `points` collection in the
    given database. Note that this always uses the collection `points` when uploading the documents.

    :param dict perf_json: The raw data json file from Evergreen mapped to a Python dictionary.
    :param str mongo_uri: The uri to connect to the cluster.
    :param str database: The name of the database in the cluster to use.
    """
    db = MongoClient(mongo_uri).get_database(database)
    collection = db.points
    points = _translate_points(perf_json)
    if points:
        collection.insert(points)


def _translate_points(perf_json):
    """
    Take the data from perf_json and extract the necessary information to create documents for the
    `points` collection.

    :param dict perf_json: The raw data json file from Evergreen mapped to a Python dictionary.
    :return: A list of dictionaries representing the documents for the `points` collection.
    """
    points = []
    for test_result in perf_json['data']['results']:
        point = {}
        point['project'] = perf_json['project_id']
        point['task'] = perf_json['task_name']
        point['task_id'] = perf_json['task_id']
        point['variant'] = perf_json['variant']
        point['version_id'] = perf_json['version_id']
        point['revision'] = perf_json.get('revision', 'patch_build')
        point['order'] = perf_json['order']
        point['start'] = test_result['start']
        point['end'] = test_result['end']
        point['test'] = test_result['name']
        # Microbenchmarks does not produce a 'workload' field. We need to fill in the 'workload'
        # field for microbenchmark points in order to query on 'workload'.
        point['workload'] = test_result.get('workload', 'microbenchmarks')
        point['max_thread_level'], point['max_ops_per_sec'] = _get_max_ops_per_sec(test_result)
        point['results'] = _get_thread_levels(test_result)
        points.append(point)
    return points


def _get_thread_levels(test_result):
    """
    Extract and sort the thread level and respective results from the raw data file from Evergreen.
    See below for an example of the resulting format:

        [
            {
                'thread_level': '1',
                'max_ops_per_sec': 500,
                'ops_per_sec': [
                    500
                ]
            },
            {
                'thread_level: '2',
                'max_ops_per_sec': 700,
                'ops_per_sec': [
                    700
                ]
            }
        ]

    :param dict test_result: All the test results from the raw data file from Evergreen.
    :return: A list of dictionaries with test results organized by thread level.
    """
    thread_levels = []
    for thread_level, result in test_result['results'].items():
        if isinstance(result, dict):
            this_result = copy.deepcopy(result)
            this_result.pop('error_values', None)
            this_result.update({'thread_level': thread_level})
            thread_levels.append(this_result)
    return sorted(thread_levels, key=lambda k: k['thread_level'])


def _get_max_ops_per_sec(test_result):
    """
    For a given set of test results, find and return the maximum operations per second metric and
    its respective thread level.

    :param dict test_result: All the test results from the raw data file from Evergreen.
    :return: The maximum operations per second found and its respective thread level.
    :rtype: tuple(int, int).
    """
    max_ops_per_sec = None
    max_thread_level = None
    for key, thread_level in test_result['results'].iteritems():
        if not key.isdigit():
            continue
        if max_ops_per_sec == None or max_ops_per_sec < thread_level['ops_per_sec']:
            max_ops_per_sec = thread_level['ops_per_sec']
            max_thread_level = int(key)
    return max_thread_level, max_ops_per_sec


def _extract_tests(perf_json):
    """
    Extract the test names from the raw data file from Evergreen.

    :param dict perf_json: The raw data json file from Evergreen mapped to a Python dictionary.
    """
    return set([ it['name'] for it in perf_json['data']['results'] ])


def _create_descriptor(perf_json, test):
    """
    Print a description of the relevant test.

    :param dict perf_json: The raw data json file from Evergreen mapped to a Python dictionary.
    :param str test: The name of the test.
    """
    return "{}/{}/{}/{}".format(perf_json['project_id'],
                                perf_json['variant'],
                                perf_json['task_name'],
                                test)


class PointsModel(object):
    """
    Model that gathers the point data and runs QHat to find change points.
    """

    def __init__(self, perf_json, mongo_uri, database, limit=None, pvalue=None):
        """
        :param dict perf_json: The raw data json file from Evergreen mapped to a Python dictionary.
        :param str mongo_uri: The uri to connect to the cluster.
        :param str database: The name of the database in the cluster to use.
        :param limit: The limit for the number of points to retrieve from the database.
        :type: int, None.
        :param pvalue: The pvalue for the QHat algorithm.
        :type: int, float, None.
        """
        self.perf_json = perf_json
        self.db = MongoClient(mongo_uri).get_database(database)
        self.limit = limit
        self.pvalue = pvalue

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
        query = OrderedDict([
            ('project', self.perf_json['project_id']),
            ('variant', self.perf_json['variant']),
            ('task', self.perf_json['task_name']),
            ('test', test)
        ])
        projection = {'max_ops_per_sec': 1, 'revision': 1, 'order': 1, '_id': 0}

        cursor = self.db.points.find(query, projection).sort([('order', pymongo.ASCENDING)])

        if self.limit is not None:
            cursor.limit(self.limit)

        series = []
        revisions = []
        orders = []

        many_points = 0
        # TODO: `PERF-1506: Create a series for each thread level when passing data into the QHat
        # algorithm`.
        for point in cursor:
            series.append(point['max_ops_per_sec'])
            revisions.append(point['revision'])
            orders.append(point['order'])
            many_points += 1

        return series, revisions, orders, query, many_points

    def compute_change_points(self, test):
        """
        Compute the change points for the given test using the QHat algorithm and insert them into
        the `change_points` collection of the database.

        :param str test: The name of the test.
        :return: The number of points for the test, the number of change points found by the QHat
        algorithm, and the time taken for this method to run.
        :rtype: tuple(int, int, float)
        """
        started_at = int(round(time.time() * 1000))

        series, revisions, orders, query, many_points = self.get_points(test)

        change_points = QHat({
            'series': series,
            'revisions': revisions,
            'orders': orders,
            'testname': test
        }, pvalue=self.pvalue).change_points
        many_change_points = len(change_points)

        # TODO: Revisit implementation of insert.
        bulk = self.db.change_points.initialize_ordered_bulk_op()
        bulk.find(query).remove()

        for point in change_points:
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

    def __init__(self, perf_json, mongo_uri, database):
        """
        :param dict perf_json: The raw data json file from Evergreen mapped to a Python dictionary.
        """
        self.perf_json = perf_json
        self.mongo_uri = mongo_uri
        self.database = database

    def run(self):
        """
        Run the analysis to compute any change points with the new data.
        """
        model = PointsModel(self.perf_json, self.mongo_uri, self.database)
        for test in _extract_tests(self.perf_json):
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
        descriptor = _create_descriptor(self.perf_json, test).ljust(120)
        print("{0}: {1:1} -> {2:2} {3:3,}ms".format(descriptor,
                                                    many_points,
                                                    many_change_points,
                                                    duration))


def main():
    log.setup_logging(True, None)
    config = ConfigDict('analysis')
    config.load()
    evg_client = evergreen_client.Client()
    perf_json = evg_client.query_perf_results(config['runtime']['task_id'])
    mongo_uri = config['analysis']['mongo_uri']
    database = 'perf'
    if not config['runtime'].get('is_patch', False):
        _upload_json(perf_json, mongo_uri, database)
    changes_driver = DetectChangesDriver(perf_json, mongo_uri, database)
    changes_driver.run()


if __name__ == '__main__':
    main()
