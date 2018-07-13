"""
Common Command helpers and objects.
"""
import functools
import os
import re
from collections import OrderedDict

# pylint: disable=too-many-instance-attributes,too-many-arguments,too-few-public-methods
from datetime import datetime, timedelta

from bson.json_util import RELAXED_JSON_OPTIONS, dumps
from pymongo import MongoClient
from pymongo.uri_parser import parse_uri

DEFAULT_KEY_ORDER = ('_id', 'revision', 'project', 'variant', 'task', 'test', 'thread_level',
                     'processed_type')
"""
The default keys used by :method: 'order'.
"""

PROCESSED_TYPE_HIDDEN = "hidden"
"""
The processed_type value for a hidden processed change point.
"""

PROCESSED_TYPE_ACKNOWLEDGED = "acknowledged"
"""
The processed_type value for an acknowledged processed change point.
"""

PROCESSED_TYPES = [PROCESSED_TYPE_HIDDEN, PROCESSED_TYPE_ACKNOWLEDGED]
"""
The list of recommended procssed_types for a processed change point.
"""


class CommandConfiguration(object):
    """
    Common Configuration for commands.
    """

    def __init__(self, debug, out, file_format, mongo_uri, queryable, dry_run, compact, points,
                 change_points, processed_change_points, build_failures):
        """
        Create the command configuration.

        :param int debug: The debug level.
        :param str out: The output directory.
        :param str file_format: The file format.
        :param str mongo_uri: The mongo db uri. This also contains the database name.
        :param bool queryable: Print identifiers as cut and paste query.
        :param bool dry_run: Don't run the command, just print what would be done.
        :param bool compact: if True display json in a compact format. Otherwise expanded.
        :param str points: The points collection name.
        :param str change_points: The change points collection name.
        :param str processed_change_points: The processed change points collection name.
        :param str build_failures: The build failures collection name.
        """
        self.debug = debug
        self.out = os.path.expandvars(os.path.expanduser(out))
        self.format = file_format
        self.mongo_uri = mongo_uri
        self.queryable = queryable
        self.dry_run = dry_run
        self.compact = compact

        self._mongo_client = None

        self._database = None
        uri = parse_uri(mongo_uri)
        self.database_name = uri['database']

        self._points = None
        self.points_name = points

        self._change_points = None
        self.change_points_name = change_points

        self._processed_change_points = None
        self.processed_change_points_name = processed_change_points

        self._build_failures = None
        self.build_failures_name = build_failures

    @property
    def mongo_client(self):
        """
        Get the mongo client instance.

        :return: MongoClient.
        """
        if self._mongo_client is None:
            self._mongo_client = MongoClient(self.mongo_uri)
        return self._mongo_client

    @property
    def database(self):
        """
        Get the database instance for self.database_name.

        :return: database.
        """
        if self._database is None:
            self._database = self.mongo_client.get_database(self.database_name)
        return self._database

    @property
    def points(self):
        """
        Get the collection instance for self.database_name / self.points_name.

        :return: collection.
        """
        if self._points is None:
            self._points = self.database.get_collection(self.points_name)
        return self._points

    @property
    def change_points(self):
        """
        Get the collection instance for self.database_name / self.change_points_name.

        :return: collection.
        """
        if self._change_points is None:
            self._change_points = self.database.get_collection(self.change_points_name)
        return self._change_points

    @property
    def processed_change_points(self):
        """
        Get the collection instance for self.database_name / self.processed_change_points_name.

        :return: collection.
        """
        if self._processed_change_points is None:
            self._processed_change_points = \
                self.database.get_collection(self.processed_change_points_name)
        return self._processed_change_points

    @property
    def build_failures(self):
        """
        Get the collection instance for self.database_name / self.build_failures_name.

        :return: collection.
        """
        if self._build_failures is None:
            self._build_failures = \
                self.database.get_collection(self.build_failures_name)
        return self._build_failures


def flags_to_value(flags):
    """
    Take a string of Regex flags and convert to int. For example:
    "/find me/mi" has the flags 'mi' and would return re.M | re.I.

    :param str flags: The string of flags. "mi" in the following pattern "/find me/mi".
    :return: int bitwise OR of the flags.
    """
    names = vars(re)
    values = [names[flag] for flag in flags.upper() if flag in names]
    return functools.reduce(lambda x, y: x | y, values, 0)


def extract_pattern(parameter, string_is_pattern=False):
    """
    Take a command line argument and converts it to a python re.

    :param parameter: The parameter value to convert. This uses
    `re.match <https://docs.python.org/2/library/re.html#re.match>' internally. Not strictly PCRE,
    see `Regular Expression HOWTO<https://docs.python.org/2/howto/regex.html#regex-howto>' and
    try to stick to simple patterns.
    :type parameter:  str, None.

    :param bool string_is_pattern: Denotes that all strings are patterns.
    :return: re or Falsey (None or '').
    """
    if parameter:
        if parameter[0] == '/' or string_is_pattern:
            if parameter[0] == '/':
                end = parameter.rfind('/')
                pattern = parameter[1:end]
                flags = parameter[end + 1:]
            else:
                flags = ""
                pattern = parameter
            parameter = re.compile(pattern, flags_to_value(flags))
    return parameter


def process_params(revision, project, variant, task_name, test, thread_level):
    # pylint: disable=too-many-arguments
    """
    Convert the command line parameters to a query. Parameters are converted according to the
    following rules:
       * None or '' (empty string) then that parameter key is filtered from the match.
       * strings starting with '/' are patterns and are matched as such.
       * all other strings are exact matches.

    :param revision: The revision to match.
    :type revision: str, None.
    :param project: The project to match.
    :type project: str, None.
    :param variant: The variant to match.
    :type variant: str, None.
    :param task_name: The task to match.
    :type task_name: str, None.
    :param test: The test to match.
    :type test: str, None.
    :param thread_level: The thread_level to match.
    :type thread_level: str, None.
    :return: dict.

    """
    params = {
        "revision": extract_pattern(revision),
        "project": extract_pattern(project),
        "variant": extract_pattern(variant),
        "task": extract_pattern(task_name),
        "test": extract_pattern(test),
        "thread_level": extract_pattern(thread_level)
    }
    match = {k: v for (k, v) in params.items() if v}
    return match


def process_excludes(excludes):
    """
    Convert excludes into a list of re.

    :param list(str) excludes: The exclude string.
    :return: list(re).
    """
    return [extract_pattern(pattern, True) for pattern in excludes]


def order(point, keys=None):
    """
    Create an OrderedDict for printing. We want the useful information to be printed first.

    :param dict point: The point  to order.
    :param list(str) or None keys: Print these keys first (if the key is present). If keys is None
    the list defaults to :const: `DEFAULT_KEY_ORDER`..
    :return OrderedDict.
    """
    if keys is None:
        keys = DEFAULT_KEY_ORDER
    ordered_point = OrderedDict((key, point[key]) for key in keys if key in point)
    ordered_point.update((key, point[key]) for key in sorted(point.keys()) if key not in keys)
    return ordered_point


def stringify_json(point, compact=False, keys=None):
    """
    Stringify point.

    :param dict point: The point  to order.
    :param bool compact: Convert to a single line string if compact is True otherwise a multi-line
    4 space indented
    `extended json<https://docs.mongodb.com/manual/reference/mongodb-extended-json/index.html>'
    string is produced.
    For keys, see :method: `order`.

    :return str.
    """
    json_args = {'json_options': RELAXED_JSON_OPTIONS}
    if not compact:
        json_args.update({'indent': 4, 'separators': (',', ': ')})
    return dumps(order(point, keys=keys), **json_args)


def filter_excludes(points, keys, exclude_patterns):
    """
    A generator to check each point and filter out any thing that has a key value that matches any
    of the exclude_patterns.

    The following example yields all the points which are not a bestbuy_query task or mixed_insert
    test.

    It can be used as an iterator:

        keys = ["test", "task"]
        excludes = [re.compile('/^bestbuy_query/'),
                    re.compile('/^mixed_insert/')]
        for point in filter_excludes(collection.find(query), keys, excludes):
          print(point)

    Note: it will aso check bestbuy_query against the test and mixed_insert against the task. In
    both cases, there is no overlap, but be aware that this can happen.

    Or if you need a list just use:

      points = list(filter_excludes(collection.find(query), keys, excludes))

    :param points: The full points without data that matches any of excludes patterns.
    :type points: iterator(dict).
    :param list(str) keys: A list of the key to check against the excludes.
    :param list(re) exclude_patterns: The filter patterns to exclude.
    :return: The points without data that matches any of excludes patterns.
    :rtype: iterator(dict).
    """

    for point in points:
        if not any(k for k, v in point.items() for pattern in exclude_patterns
                   if k in keys and pattern.match(v)):
            yield point


def item_show_func(task_identifier):
    """
    Show task in progressbar status.

    :param task_identifier: The 'project', 'variant', 'task', and 'task' values.
    :type task_identifier: None, dict.
    :return: The project, variant and task fields (in this order) joined by '/' .
    :rtype: str, None.
    """
    if task_identifier and isinstance(task_identifier, dict):
        return '/'.join(task_identifier[k] for k in reversed(['project', 'variant', 'task']))
    return None


def get_matching_tasks(points, query, no_older):
    """
    Get all the tasks in the point collection that match project, variant, task, test and have
    data newer than no_older.

    :param collection points: The points collection.
    :param dict query: The query to use (generated from command line params).
    :param int no_older: Filter tasks only with data older than this.
    :return: Unique matching tasks.
    :rtype: list(dict).
    """
    old = datetime.now() - timedelta(days=no_older)
    query['start'] = {"$gt": int(old.strftime('%s'))}
    pipeline = [{
        '$match': query
    }, {
        '$group': {
            '_id': {
                'project': '$project',
                'variant': '$variant',
                'task': '$task'
            },
            'tests': {
                '$addToSet': '$test'
            }
        }
    }, {
        '$sort': {
            "_id.project": 1,
            "_id.variant": 1,
            "_id.task": 1
        }
    }, {
        '$project': {
            "project": "$_id.project",
            "variant": "$_id.variant",
            "task": "$_id.task",
            "tests": 1,
            "_id": 0
        }
    }]
    return points.aggregate(pipeline)


def filter_tests(test_name, excludes):
    """
    Filter test based on excludes.

    :param str test_name: The test name.
    :param list(re) excludes: The list of exclude patterns to match against.
    :return: True if any of the excludes match test_name.
    :rtype: bool.
    """
    return any([pattern.match(test_name) for pattern in excludes])


def filter_legacy_tasks(tasks):
    """
    Filter tasks that end with _WT or _MMAPv1. This is a generator so can be used as an iterator.
    If the results are needed as a list then make on:
        l = list(filter_legacy_tasks(tasks, task_identifier))

    :param tasks: A list of task dict identifiers (project / variant / task / test) tuple. It must
    contain a 'task' field.
    :type tasks: iterator(dict)
    :return: The non legacy tasks.
    :rtype: iterator(dict).
    """
    for task in tasks:
        name = task['task']
        if not name.endswith('_WT') and not name.endswith('_MMAPv1'):
            yield task


def generate_tests(matching_tasks):
    """
    Unwind matching each tasks tests, sorted by task and test. This method yields the elements, so
    it can be used as an iterator or as a list as follows:

        # iterator
        for test in generate_tests(matching_tasks):
            pass
        # list
        tests = list(generate_tests(matching_tasks))

    :param list(dict) matching_tasks: The task identifier and grouped tests.
    :return: This function yields a dict for each value in the 'tests' field. Each dict is a copy
    of the task with the 'tests' field removed and a 'test' new field (for each test name).
    :rtype: generator(dict).
    """
    for task_identifier in matching_tasks:
        for test_name in sorted(task_identifier['tests']):
            test_identifier = task_identifier.copy()
            test_identifier['test'] = test_name
            del test_identifier['tests']
            yield test_identifier
