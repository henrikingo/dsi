"""
Task etl helper methods. This loads the translated task to a mongodb.
"""
import copy
import urlparse

import pymongo
import structlog

LOG = structlog.get_logger(__name__)


def make_filter(point):
    """
    Given a datapoint make a document that just has fields that uniquely identify this point,
    removing extra information. Used for filter in upsert.

    """
    filter_keys = ['project', 'task', 'variant', 'test', 'version_id', 'revision']
    mongo_filter = {key: point[key] for key in filter_keys}
    LOG.debug("Made filter", filter=mongo_filter)
    return mongo_filter


def load(perf_json, mongo_uri, tests=None):
    """
    Take the perf_json data, create documents and upsert / update the data in the `points`
    collection in the given database.

    Note the operations runs in a transaction and the code takes care to update the documents
    without overwriting previous state (like outlier and rejected status).

    Note that this always uses the collection `points` when uploading the documents.

    :param dict perf_json: The raw data json file from Evergreen mapped to a Python dictionary.
    :param str mongo_uri: The uri to connect to the cluster.
    :param tests: The tests from `perf_json` to upload. Note that if tests == None, all tests are
    uploaded.
    :type: dict, None.
    """
    # pylint: disable=invalid-name
    points = translate_points(perf_json, tests)
    try:
        db = pymongo.MongoClient(mongo_uri).get_database()
        collection = db.points
        client = db.client
        if points:
            requests = [operation for point in points for operation in make_updates(point)]

            with client.start_session() as session:
                with session.start_transaction():
                    bulk_write_result = collection.bulk_write(requests, ordered=True)

            LOG.debug("load bulk_write", results=bulk_write_result.bulk_api_result)
        else:
            LOG.debug("load bulk_write no points")
    except Exception as e:
        # pylint: disable=no-member
        LOG.warn(
            'load failed.', exc_info=True, details=e.details if hasattr(e, 'details') else str(e))
        raise


def make_updates(point):
    """
    make the expected set of upsert and update operations for this point.

    :param dict point: The point data.
    :return: A list of expected updates.
    """
    insert_operation = point.copy()
    results = insert_operation.pop('results') if 'results' in insert_operation else []

    operations = [
        pymongo.UpdateOne(
            make_filter(point), {'$set': insert_operation,
                                 '$setOnInsert': {
                                     'results': results
                                 }},
            upsert=True)
    ]

    for result in results:
        query = make_filter(point)
        query['results.thread_level'] = result['thread_level']

        operation = {'results.$.{k}'.format(k=k): v for k, v in result.items()}
        operations.append(pymongo.UpdateOne(query, {'$set': operation}))
    return operations


def _filter_non_test_results(results):
    """
    Remove non-results data from a results section of a test_results dict.

    This will filter out the 'start' and 'end' keys.

    :param results: results section to filter.
    :return: results with non-results data filtered out.
    """
    ignored_keys = {'start', 'end'}
    return {k: v for k, v in results.items() if k not in ignored_keys}


def _is_valid_result(test_result, tests):
    """
    Determine if the given test_result contains valid data.

    :param test_result: test_result to check.
    :param tests: List of tests to upload.
    :return: True if the test_result contains valid data.
    """
    if tests is not None and test_result['name'] not in tests:
        return False

    if 'start' not in test_result and 'start' not in test_result['results']:
        return False

    results = _filter_non_test_results(test_result['results'])
    if all('ops_per_sec' not in result for _, result in results.items()):
        LOG.warn('no ops_per_sec, skipping', test_result=test_result)
        return False

    return True


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
        if not _is_valid_result(test_result, tests):
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
    results = _filter_non_test_results(test_result['results'])
    for key, thread_level in results.items():
        if not key.isdigit():
            LOG.warn(
                'Invalid thread level value found', results_item_key=key, thread_level=thread_level)
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


def create_descriptor(perf_json, test=None):
    """
    Create a description for the relevant test.

    :param dict perf_json: The raw data json file from Evergreen mapped to a Python dictionary.
    :param str test: The name of the test.
    """
    parts = []
    parts.append(perf_json['project_id'] if 'project_id' in perf_json else perf_json['project'])
    parts.append(perf_json['variant'])
    parts.append(perf_json['task_name'] if 'task_name' in perf_json else perf_json['task'])
    parts.append(test if test is not None else perf_json['test'])
    if 'thread_level' in perf_json:
        parts.append(perf_json['thread_level'])
    return '/'.join(parts)


def redact_url(url):
    """
    Redact a url so that is can be logged.

    :param str url: The url to redact.
    """
    parsed = urlparse.urlparse(url)
    if parsed.password:
        replaced = parsed._replace(
            netloc="{}:{}@{}".format(parsed.username, "???", parsed.hostname))
    else:
        replaced = parsed
    return replaced.geturl()
