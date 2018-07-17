"""
Task etl helper methods. This loads the translated task to a mongodb.
"""
import copy
import logging

import pymongo

from bin.common import config

LOG = logging.getLogger(__name__)


def load(perf_json, mongo_uri, tests=None):
    """
    Take the data from perf_json, create documents and upload them to the `points` collection in the
    given database. Note that this always uses the collection `points` when uploading the documents.

    :param dict perf_json: The raw data json file from Evergreen mapped to a Python dictionary.
    :param str mongo_uri: The uri to connect to the cluster.
    :param tests: The tests from `perf_json` to upload. Note that if tests == None, all tests are
    uploaded.
    :type: dict, None.
    """
    # pylint: disable=invalid-name
    db = pymongo.MongoClient(mongo_uri).get_database()
    collection = db.points
    points = translate_points(perf_json, tests)
    if points:
        collection.insert(points)


def translate_points(perf_json, tests):
    """
    Take the data from perf_json and extract the necessary information to create documents for the
    `points` collection.

    :param dict perf_json: The raw data json file from Evergreen mapped to a Python dictionary.
    :param tests: The tests from `perf_json` to upload. Note that if tests == None, all tests are
    uploaded.
    :type: dict, None.
    :return: A list of dictionaries representing the documents for the `points` collection.
    """
    points = []
    for test_result in perf_json['data']['results']:
        if tests is not None and test_result['name'] not in tests:
            continue
        point = {}
        point['project'] = perf_json['project_id']
        point['task'] = perf_json['task_name']
        point['task_id'] = perf_json['task_id']
        point['variant'] = perf_json['variant']
        point['version_id'] = perf_json['version_id']
        point['revision'] = perf_json.get('revision', 'patch_build')
        point['order'] = perf_json['order']
        point['create_time'] = perf_json['create_time']
        # Microbenchmarks stores the 'start' and 'end' time of the test in the inner 'results' field
        # while sys-perf stores it in the outer 'results' field.
        point['start'] = test_result['start'] if 'start' in test_result else test_result['results'][
            'start']
        point['end'] = test_result['end'] if 'end' in test_result else test_result['results']['end']
        point['test'] = test_result['name']
        # Microbenchmarks does not produce a 'workload' field. We need to fill in the 'workload'
        # field for microbenchmark points in order to query on 'workload'.
        point['workload'] = test_result.get('workload', 'microbenchmarks')
        point['max_thread_level'], point['max_ops_per_sec'] = _get_max_ops_per_sec(test_result)
        # Do not add a test with an invalid thread level.
        if point['max_ops_per_sec'] is None:
            continue
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
                'ops_per_sec': 500,
                'ops_per_sec': [
                    500
                ]
            },
            {
                'thread_level: '2',
                'ops_per_sec': 700,
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
        if not config.is_integer(key) and key != 'start' and key != 'end':
            LOG.warn('Invalid thread level value %s found', key)
            continue
        elif key == 'start' or key == 'end':
            continue
        if max_ops_per_sec is None or max_ops_per_sec < thread_level['ops_per_sec']:
            max_ops_per_sec = thread_level['ops_per_sec']
            max_thread_level = int(key)
    return max_thread_level, max_ops_per_sec


def extract_tests(perf_json):
    """
    Extract the test names from the raw data file from Evergreen.

    :param dict perf_json: The raw data json file from Evergreen mapped to a Python dictionary.
    """
    return set([it['name'] for it in perf_json['data']['results']])


def create_descriptor(perf_json, test):
    """
    Print a description of the relevant test.

    :param dict perf_json: The raw data json file from Evergreen mapped to a Python dictionary.
    :param str test: The name of the test.
    """
    return "{}/{}/{}/{}".format(perf_json['project_id'], perf_json['variant'],
                                perf_json['task_name'], test)