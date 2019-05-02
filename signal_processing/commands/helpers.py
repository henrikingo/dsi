"""
Common Command helpers and objects.
"""
from copy import deepcopy
import functools
import os
import re
from collections import OrderedDict

# pylint: disable=too-many-instance-attributes,too-many-arguments,too-few-public-methods
# pylint: disable=too-many-lines
from datetime import datetime, timedelta

import structlog
import click
import yaml

from analysis.evergreen.helpers import get_git_credentials
from bson.json_util import RELAXED_JSON_OPTIONS, dumps
from pymongo.uri_parser import parse_uri

from bin.common.utils import mkdir_p
from signal_processing.etl_helpers import redact_url, extract_tests
from signal_processing.keyring.mongo_keyring import new_mongo_client
from signal_processing.keyring.credentials import Credentials
import signal_processing.commands.jobs

PORTRAIT_FIGSIZE = (8.27, 11.69)
"""
The dimensions required to render a portrait image.
"""

LANDSCAPE_FIGSIZE = tuple(reversed(PORTRAIT_FIGSIZE))
"""
The dimensions required to render a landscape image.
"""

MAX_THREAD_LEVEL = 'max'
"""
The value of the 'thread_level' field for the max thread level.
"""

DEFAULT_KEY_ORDER = ('_id', 'suspect_revision', 'project', 'variant', 'task', 'test',
                     'thread_level', 'processed_type')
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
The list of recommended processed_types for a processed change point.
"""

LOG = structlog.getLogger(__name__)

PROCESSED_CHANGE_POINTS = 'processed_change_points'
UNPROCESSED_CHANGE_POINTS = 'unprocessed_change_points'
CHANGE_POINTS = 'change_points'
POINTS = 'points'
BUILD_FAILURES = 'build_failures'
MUTE_OUTLIERS = 'mute_outliers'
OUTLIERS = 'outliers'
MARKED_OUTLIERS = 'marked_outliers'
WHITELISTED_OUTLIER_TASKS = 'whitelisted_outlier_tasks'

DEFAULT_MONGO_URI = 'mongodb+srv://performancedata-g6tsc.mongodb.net/perf'


def read_default_config(app_name, app_conf_location):
    """
    Attempt to find and load a config file. The order is:
      1. './.{app_name}'
      2. '{app_conf_location}/.{app_name}'
      3. '{click.get_app_dir}/.{app_name}'

    :param str app_name: The application name. It is likely to be 'change-points'
    but it could be any string which generates a valid file name.
    :param str app_conf_location: A user provided directory. If will be filtered
    if None or it does not exist.
    :return: The dict from the file or {}.
    See `click.get_app_dir<http://click.pocoo.org/5/api/#click.get_app_dir>'.
    """
    application_path = click.get_app_dir(app_name, roaming=True, force_posix=True)
    if not os.path.exists(application_path) or not os.path.isfile(application_path):
        application_path = None

    app_paths = ['.', app_conf_location]
    app_paths = [
        current_path for current_path in app_paths
        if current_path is not None and os.path.exists(current_path) and os.path.isdir(current_path)
    ]

    config_file_name = ".{}".format(app_name)
    file_names = [
        file_name
        for file_name in [os.path.join(app_path, config_file_name) for app_path in app_paths]
    ]
    if application_path is not None:
        file_names += [application_path]
    file_names = [file_name for file_name in file_names if os.path.isfile(file_name)]

    config = {}
    for config_file in file_names:
        try:
            with open(config_file) as file_handle:
                config = yaml.load(file_handle)
                return config
        except:  # pylint: disable=bare-except
            LOG.warn('error loading as yml', exc_info=1)

    return config


class CommandConfiguration(object):
    # pylint: disable=too-many-instance-attributes, too-many-locals
    """
    Common Configuration for commands.
    """

    def __init__(self,
                 debug,
                 log_file,
                 out,
                 file_format,
                 mongo_uri,
                 queryable,
                 dry_run,
                 compact,
                 style,
                 mongo_repo,
                 token_file,
                 points=POINTS,
                 change_points=CHANGE_POINTS,
                 processed_change_points=PROCESSED_CHANGE_POINTS,
                 unprocessed_change_points=UNPROCESSED_CHANGE_POINTS,
                 build_failures=BUILD_FAILURES,
                 mute_outliers=MUTE_OUTLIERS,
                 outliers=OUTLIERS,
                 marked_outliers=MARKED_OUTLIERS,
                 whitelisted_outlier_tasks=WHITELISTED_OUTLIER_TASKS,
                 auth_mode=None,
                 mongo_username=None,
                 mongo_password=None):
        # pylint: disable=too-many-arguments
        """
        Create the command configuration.

        :param int debug: The debug level.
        :param str log_file: The log file.
        :param str out: The output directory.
        :param str file_format: The file format.
        :param str mongo_uri: The mongo db uri. This also contains the database name.
        :param bool queryable: Print identifiers as cut and paste query.
        :param bool dry_run: Don't run the command, just print what would be done.
        :param bool compact: if True display json in a compact format. Otherwise expanded.
        :param list(str) style: The matplotlib style(s) to use.
        :param str mongo_repo: The mongo db repo directory.
        :param str token_file: The name of the file containing the service credentials (like
        github and evergreen).
        :param str points: The points collection name.
        :param str change_points: The change points collection name.
        :param str processed_change_points: The processed change points collection name.
        :param str unprocessed_change_points: The unprocessed change points collection name.
        :param str build_failures: The build failures collection name.
        :param str mute_outliers: The mute_outliers collection name.
        :param str outliers: The outliers collection name.
        :param str marked_outliers: The marked_outliers collection name.
        :param str whitelisted_outlier_tasks: The whitelisted_outlier_tasks collection name.
        :param str auth_mode: How mongo db credentials are obtained.
        :param str mongo_username: The mongo db username.
        :param str mongo_password: The mongo db password.
        """
        if log_file is not None:
            log_file = os.path.expanduser(log_file)
        self.__setstate__({
            'debug': debug,
            'log_file': log_file,
            'out': out,
            'file_format': file_format,
            'mongo_uri': mongo_uri,
            'auth_mode': auth_mode,
            'mongodb_username': mongo_username,
            'mongodb_password': mongo_password,
            'queryable': queryable,
            'dry_run': dry_run,
            'compact': compact,
            'style': style,
            'mongo_repo': mongo_repo,
            'token_file': token_file,
            'points': points,
            'change_points': change_points,
            'processed_change_points': processed_change_points,
            'unprocessed_change_points': unprocessed_change_points,
            'build_failures': build_failures,
            'mute_outliers': mute_outliers,
            'outliers': outliers,
            'marked_outliers': marked_outliers,
            'whitelisted_outlier_tasks': whitelisted_outlier_tasks,
        })

    # pylint: disable=attribute-defined-outside-init
    @property
    def mongo_repo(self):
        """
        Get the mongo repo location if it exists.

        :return: The mongo repo directory or None.
        """
        if self._mongo_repo:
            mongo_repo = os.path.abspath(os.path.expanduser(self._mongo_repo))
            if os.path.exists(mongo_repo) and os.path.isdir(mongo_repo):
                self._mongo_repo = mongo_repo
        return self._mongo_repo

    # pylint: disable=attribute-defined-outside-init
    @property
    def credentials(self):
        """
        Get the service credentials from the token_file.

        :return: dict of credentials.
        """
        if self.token_file and self._credentials is None:
            self._credentials = get_git_credentials(self.token_file)
        return self._credentials

    # pylint: disable=attribute-defined-outside-init
    @property
    def mongo_client(self):
        """
        Get the mongo client instance.

        :return: MongoClient.
        """
        if self._mongo_client is None:
            uri = redact_url(self.mongo_uri)
            LOG.info('Create Mongo Client', uri=uri)
            credentials = None
            if self._mongo_username is not None or self._mongo_password is not None:
                credentials = Credentials(self._mongo_username, self._mongo_password)
            self._mongo_client = new_mongo_client(
                self.mongo_uri, auth_type=self.auth_mode, credentials=credentials)
        return self._mongo_client

    # pylint: disable=attribute-defined-outside-init
    @property
    def database(self):
        """
        Get the database instance for self.database_name.

        :return: database.
        """
        if self._database is None:
            self._database = self.mongo_client.get_database(self.database_name)
        return self._database

    # pylint: disable=attribute-defined-outside-init
    @property
    def points(self):
        """
        Get the collection instance for self.database_name / self.points_name.

        :return: collection.
        """
        if self._points is None:
            self._points = self.database.get_collection(self.points_name)
        return self._points

    # pylint: disable=attribute-defined-outside-init
    @property
    def change_points(self):
        """
        Get the collection instance for self.database_name / self.change_points_name.

        :return: collection.
        """
        if self._change_points is None:
            self._change_points = self.database.get_collection(self.change_points_name)
        return self._change_points

    # pylint disable=attribute-defined-outside-init
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

    # pylint disable=attribute-defined-outside-init
    @property
    def unprocessed_change_points(self):
        """
        Get the collection instance for self.database_name / self.unprocessed_change_points_name.

        :return: collection.
        """
        if self._unprocessed_change_points is None:
            self._unprocessed_change_points = \
                self.database.get_collection(self.unprocessed_change_points_name)
        return self._unprocessed_change_points

    # pylint disable=attribute-defined-outside-init
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

    # pylint disable=attribute-defined-outside-init
    @property
    def mute_outliers(self):
        """
        Get the collection instance for self.database_name / self.mute_outliers_name.

        :return: collection.
        """
        if self._mute_outliers is None:
            self._mute_outliers = \
                self.database.get_collection(self.mute_outliers_name)
        return self._mute_outliers

    # pylint disable=attribute-defined-outside-init
    @property
    def outliers(self):
        """
        Get the collection instance for self.database_name / self.outliers_name.

        :return: collection.
        """
        if self._outliers is None:
            self._outliers = \
                self.database.get_collection(self.outliers_name)
        return self._outliers

    # pylint disable=attribute-defined-outside-init
    @property
    def marked_outliers(self):
        """
        Get the collection instance for self.database_name / self.marked_outliers_name.

        :return: collection.
        """
        if self._marked_outliers is None:
            self._marked_outliers = \
                self.database.get_collection(self.marked_outliers_name)
        return self._marked_outliers

    # pylint disable=attribute-defined-outside-init
    @property
    def whitelisted_outlier_tasks(self):
        """
        Get the collection instance for self.database_name / self.whitelisted_outlier_tasks_name.

        :return: collection.
        """
        if self._whitelisted_outlier_tasks is None:
            self._whitelisted_outlier_tasks = \
                self.database.get_collection(self.whitelisted_outlier_tasks_name)
        return self._whitelisted_outlier_tasks

    def __getstate__(self):
        """
        Get state for pickle support.

        Multiprocessor uses pickle to serialize and deserialize data to the sub processes. However,
        complex types like database and collection references cannot be pickled. They can be
        recreated with the core state (and this is what this calls does).

        :return: The state to pickle.
        """
        return {
            'debug': self.debug,
            'log_file': self.log_file,
            'token_file': self.token_file,
            'out': self.out,
            'file_format': self.file_format,
            'mongo_uri': self.mongo_uri,
            'auth_mode': self.auth_mode,
            'mongodb_username': self._mongo_username,
            'mongodb_password': self._mongo_password,
            'queryable': self.queryable,
            'dry_run': self.dry_run,
            'compact': self.compact,
            'points': self.points_name,
            'change_points': self.change_points_name,
            'processed_change_points': self.processed_change_points_name,
            'unprocessed_change_points': self.unprocessed_change_points_name,
            'build_failures': self.build_failures_name,
            'mute_outliers': self.mute_outliers_name,
            'outliers': self.outliers_name,
            'marked_outliers': self.marked_outliers_name,
            'whitelisted_outlier_tasks': self.whitelisted_outlier_tasks_name,
            'style': self.style,
            'mongo_repo': self._mongo_repo
        }

    def __setstate__(self, state):
        """
        Set state for pickle support.

        Clear the lazy params like mongo client so that the are recreated on demand.

        :param dict state: The pickled state.
        """
        self.debug = state['debug']
        self.log_file = state['log_file']
        self.token_file = state['token_file']
        self.out = os.path.expandvars(os.path.expanduser(state['out']))
        self.file_format = state['file_format']
        self.mongo_uri = state['mongo_uri']
        self.auth_mode = state['auth_mode']
        self.queryable = state['queryable']
        self.dry_run = state['dry_run']
        self.compact = state['compact']

        self._mongo_username = state['mongodb_username']
        self._mongo_password = state['mongodb_password']
        self._mongo_client = None

        self._database = None
        uri = parse_uri(state['mongo_uri'])

        # TODO: argue the name in PERF-1590
        self.database_name = uri['database']

        self._points = None
        self.points_name = state['points']

        self._change_points = None
        self.change_points_name = state['change_points']

        self._processed_change_points = None
        self.processed_change_points_name = state['processed_change_points']

        self._unprocessed_change_points = None
        self.unprocessed_change_points_name = state['unprocessed_change_points']

        self._build_failures = None
        self.build_failures_name = state['build_failures']

        self._mute_outliers = None
        self.mute_outliers_name = state['mute_outliers']

        self._outliers = None
        self.outliers_name = state['outliers']

        self._marked_outliers = None
        self.marked_outliers_name = state['marked_outliers']

        self._whitelisted_outlier_tasks = None
        self.whitelisted_outlier_tasks_name = state['whitelisted_outlier_tasks']

        self.style = state['style']
        self._mongo_repo = state['mongo_repo']
        self._credentials = None

    def _redact_copy(self):
        """
        Get a copy of the state and redact any sensitive info.

        :returns: A redacted copy of the state.
        """
        copy = deepcopy(self.__getstate__())
        if 'mongo_uri' in copy:
            copy['mongo_uri'] = redact_url(copy['mongo_uri'])
        if 'mongo_password' in copy:
            copy['mongo_password'] = '*' * 8
        return copy

    def __str__(self):
        """
        Get a readable string for this job.

        :returns: A readable string.
        """
        return str(self._redact_copy())

    def __repr__(self):
        """
        Get an unambiguous string for this job.

        :returns: An unambiguous string.
        """
        return '{}.{}({!r})'.format(self.__module__, self.__class__.__name__, self._redact_copy())


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


def process_params(project, variant, task_name, test, revision=None, thread_level=None):
    # pylint: disable=too-many-arguments
    """
    Convert the command line parameters to a change points query.
    For parameters and return type see :method: `_process_params`.
    """
    return _process_params(revision, project, variant, task_name, test, thread_level,
                           'suspect_revision')


def process_params_for_points(project, variant, task_name, test, revision=None, thread_level=None):
    # pylint: disable=too-many-arguments
    # pylint: disable=too-many-arguments
    """
    Convert the command line parameters to a points query.
    For parameters and return type see :method: `_process_params`.
    """
    return _process_params(revision, project, variant, task_name, test, thread_level, 'revision')


def _process_params(revision, project, variant, task_name, test, thread_level, revision_name):
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
    :param str revision_name: The field name for revisions.
    :return: dict.

    """
    params = {
        revision_name: extract_pattern(revision),
        'project': extract_pattern(project),
        'variant': extract_pattern(variant),
        'task': extract_pattern(task_name),
        'test': extract_pattern(test),
        'thread_level': extract_pattern(thread_level)
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
    :param list keys: The key order.
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


def show_item_function(task_identifier, label_width=22, bar_width=34, info_width=70, padding=10):
    """
    Show task item in info area of progressbar status.

    :param task_identifier: An object identifying a task.
    :type task_identifier: None, dict. str.
    :param int label_width: The label width.
    :param int bar_width: The bar width.
    :param int info_width: The info width.
    :param int padding: The padding.
    :return: The project, variant and task fields (in this order) joined by '/' .
    :rtype: str, None.

    Note: label_width and bar_width are not used in this implementation, but would probably be
    required for other more rigorous implementations.
    """
    _ = label_width
    _ = bar_width

    if task_identifier and isinstance(task_identifier, signal_processing.commands.jobs.Job):
        task_identifier = task_identifier.identifier

    if task_identifier and isinstance(task_identifier, basestring):
        return str(task_identifier)

    if task_identifier and isinstance(task_identifier, dict):
        available = info_width - padding
        parts = [
            task_identifier[k] for k in ['project', 'variant', 'task', 'test', 'thread_level']
            if k in task_identifier and task_identifier[k] is not None
        ]
        parts.reverse()
        info = '/'.join(parts)
        while len(info) > available:
            parts.pop()
            info = '/'.join(parts)
            if len(parts) == 1:
                break
        return info
    return None


def get_bar_template(label_width, bar_width, info_width):
    """
    Get a format for the progress bar.

    :param int label_width: The width of the label (LHS) portion of the progress bar.
    :param int bar_width: The width of the progress (center) portion of the bar.
    :param int info_width: The width of the info (RHS) portion of the bar.
    :return: A format string, like '%(label)-10.10s [%(bar)20.20s] %(info)-10.10s'.
    """
    bar_template = '%(label)-{0}.{0}s [%(bar){1}.{1}s] %(info)-{2}.{2}s'.format(
        label_width, bar_width, info_width)
    return bar_template


def query_terminal_for_bar():
    """
    Query the current terminal and get a bar_template and show item function for this
    configuration.

    :return: bar_template and show_label_function.
    """
    label_width, bar_width, info_width, padding = get_bar_widths()
    bar_template = get_bar_template(label_width, bar_width, info_width)
    bound_show_item_function = functools.partial(
        show_item_function,
        label_width=label_width,
        bar_width=bar_width,
        info_width=info_width,
        padding=padding)
    return bar_template, bound_show_item_function


# TODO: As part of PERF-1638 this function needs to be put in a file where it is
# appropriate to know about click. It is possible but not worth the effort to write
# click.get_terminal_size ourselves.
def get_bar_widths(label_width=22, max_bar_width=34, max_info_width=75, padding=10, width=None):
    """
    Get progress bar widths so as to fit on a terminal line (with a little padding).

    :param int label_width: The max width of the label (LHS) portion of the progress bar.
    :param int max_bar_width: The max width of the progress (center) portion of the bar.
    :param int max_info_width: The max width of the info (RHS) portion of the bar.
    :param width: The actual terminal width or None (None => get the width).
    :type width: int, None.
    :param int padding: The padding for the bar.
    :return: Updated label_width, bar_width, info_width, padding to fit the line.
    :rtype: (int,int,int,int).
    """
    if width is None:
        width, _ = click.get_terminal_size()
    width = width - 4 - label_width - padding
    bar_width = min(width / 2, max_bar_width)
    info_width = min(width - bar_width, max_info_width)
    return label_width, bar_width, info_width, padding


def get_query_for_points(test_identifier):
    """ Create a points query from a test identifier.

    :param dict test_identifier: The project / variant / task / test and thread level values.

    :return: A query to get the points for this identifier.
    :rtype: dict
    """
    points_query = test_identifier.copy()
    if 'thread_level' in test_identifier:
        thread_level = test_identifier['thread_level']
        del points_query['thread_level']

        # The max_ops_per_sec is the correct value, so we don't need results.thread_level.
        if thread_level != MAX_THREAD_LEVEL:
            points_query['results.thread_level'] = thread_level
    return points_query


def get_matching_tasks(points, test_identifier, no_older=None):
    """
    Get all the tasks in the point collection that match project, variant, task, test and have
    data newer than no_older.

    :param collection points: The points collection.
    :param dict test_identifier: The test identifier to use (generated from command line params).
    :param no_older: Filter tasks only with data older than this. If no value is supplied then
    don't filter on start time.
    :type no_older: int, None.
    :return: Unique matching tasks.
    :rtype: pymongo.Cursor.
    """
    query = get_query_for_points(test_identifier)
    if no_older is not None:
        old = datetime.now() - timedelta(days=no_older)
        query['start'] = {'$gt': int(old.strftime('%s'))}
    add_revision = 'revision' in query
    pipeline = [{'$match': query}]
    grouping = {
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
    }
    if add_revision:
        grouping['$group']['_id']['revision'] = '$revision'
    pipeline.append(grouping)
    pipeline.append({'$sort': {'_id.project': 1, '_id.variant': 1, '_id.task': 1}})

    projection = {
        '$project': {
            'project': '$_id.project',
            'variant': '$_id.variant',
            'task': '$_id.task',
            'tests': 1,
            '_id': 0
        }
    }

    if add_revision:
        projection['$project']['revision'] = '$_id.revision'
    pipeline.append(projection)

    return points.aggregate(pipeline)


def get_matching_change_points(change_points, test_identifier):
    """
    Get all the tasks in the change points collection that match project, variant, task, test.

    :param collection change_points: The change_points collection.
    :param dict test_identifier: The test identifier to use (generated from command line params).
    :return: Unique matching tasks.
    :rtype: pymongo.Cursor.
    """
    query = test_identifier
    pipeline = [{
        '$match': query
    }, {
        '$group': {
            '_id': {
                'suspect_revision': '$suspect_revision',
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
            '_id.suspect_revision': 1,
            '_id.project': 1,
            '_id.variant': 1,
            '_id.task': 1
        }
    }, {
        '$project': {
            'suspect_revision': '$_id.suspect_revision',
            'project': '$_id.project',
            'variant': '$_id.variant',
            'task': '$_id.task',
            'tests': 1,
            '_id': 0
        }
    }]

    return change_points.aggregate(pipeline)


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


def save_plot(figure, pathname, filename):
    """
    Save the figure in filename in pathname. Pathname is created if it does not exist.

    :param object figure: The figure to save.
    :param str pathname: The pathname to save in it.
    :param str filename: The filename to save it in.
    """
    mkdir_p(pathname)
    full_filename = os.path.join(pathname, filename)
    figure.savefig(full_filename)


# TODO: As part of PERF-1638 this function needs to be put in a file where it is
# appropriate to know about click. This is called by click so
# click.BadParameter is the correct exception.
def validate_int_none_options(context, param, value):
    """
    Validate that the limit value is either an integer or 'None'.

    :param object context: The click context object.
    :param object param: The click parameter definition.
    :param str value: The value for the --limit option.
    :return: The validated limit value. Either an integer or None for no limit.
    :rtype: int or None.
    :raises: click.BadParameter if the parameter is not valid.
    """
    #pylint: disable=unused-argument
    try:
        if isinstance(value, basestring) and value.lower() == "none":
            return None
        return int(value)
    except ValueError:
        pass
    raise click.BadParameter('{} is not a valid integer or None.'.format(value))


def _assert_valid_outlier_percentage(percentage):
    """
    Validate that percentage is a valid numeric type between 0 and 1 (inclusive).

    :raises: ValueError if percentage is invalid.
    """
    if not isinstance(percentage, (float, int)) or percentage < 0 or percentage > 1.0:
        raise ValueError()


def validate_outlier_percentage(context, param, value):
    """
    Validate that the value is None or between 0 and 1 (inclusive).

    :param object context: The click context object.
    :param object param: The click parameter definition.
    :param str value: The value for the --limit option.
    :return: The validated limit value.
    :rtype: float.
    :raises: click.BadParameter if the parameter is not valid.
    """
    #pylint: disable=unused-argument
    try:
        if value is not None:
            _assert_valid_outlier_percentage(value)
        return value
    except ValueError:
        pass
    raise click.BadParameter(
        '{} is not a valid outlier percentage (between 0 and 1.0) or None.'.format(value))


def validate_outlier_percentages(context, param, value):
    """
    Validate that all the floats in value are between 0 and 1 (inclusive).

    :param object context: The click context object.
    :param object param: The click parameter definition.
    :param str value: The value for the --limit option.
    :return: The validated limit value.
    :rtype: float.
    :raises: click.BadParameter if the parameter is not valid.
    """
    #pylint: disable=unused-argument
    try:
        for percentage in value:
            _assert_valid_outlier_percentage(percentage)
        return value
    except ValueError:
        pass
    raise click.BadParameter(
        '{} are not valid outlier percentages (between 0 and 1.0).'.format(value))


def extract_test_identifiers(perf_json):
    """
    Extract the test identifiers from the raw data file from Evergreen.

    :param dict perf_json: The raw data json file from Evergreen mapped to a Python dictionary.
    """
    project = perf_json['project_id']
    variant = perf_json['variant']
    task = perf_json['task_name']
    return [{
        'project': project,
        'variant': variant,
        'task': task,
        'test': test
    } for test in extract_tests(perf_json)]


def _matches(pattern_or_string, thread_level):
    """
    Match a pattern, string or None to the thread level.

    :param pattern_or_string: The pattern or string to match against.
    :type pattern_or_string: re.pattern, string or None.
    :param string thread_level: The thread level
    :return: True if pattern is None, regex matches thread level or string matches thread level.
    """
    if pattern_or_string is None:
        return True
    if isinstance(pattern_or_string, basestring):
        return pattern_or_string == thread_level
    if isinstance(pattern_or_string, type(re.compile(''))):
        return pattern_or_string.match(thread_level)
    return False


def generate_thread_levels(test_identifier, points_collection, thread_level=None):
    """
    Given a test identifier of project / variant / task and test, get the thread levels from
    the points collection.

    :param dict test_identifier: The project / variant / task and test.
    :param pymongo.Collection points_collection: The points collection ref.
    :param re.pattern thread_level: A thread level pattern or None for all.
    """

    pipeline = [{
        '$match': test_identifier
    }, {
        '$unwind': '$results'
    }, {
        '$group': {
            '_id': {
                'project': '$project',
                'variant': '$variant',
                'task': '$task',
                'test': '$test',
                'thread_level': '$results.thread_level'
            }
        }
    }, {
        '$project': {
            '_id': 0,
            'project': '$_id.project',
            'variant': '$_id.variant',
            'task': '$_id.task',
            'test': '$_id.test',
            'thread_level': '$_id.thread_level'
        }
    }]
    levels = list(points_collection.aggregate(pipeline))

    for identifier in levels:
        if _matches(thread_level, identifier['thread_level']):
            yield identifier
    if len(levels) > 1 and _matches(thread_level, MAX_THREAD_LEVEL):
        max_level = levels[0].copy()
        max_level['thread_level'] = MAX_THREAD_LEVEL
        yield max_level


def is_max_thread_level(test_identifier):
    """
    Check if a test identifier is for the max thread level.

    :return: true if thread_level is set and equal to MAX_THREAD_LEVEL.
    """
    return test_identifier.get('thread_level', None) == MAX_THREAD_LEVEL


def validate_outlier_param(context, param, value):
    """
    Validate that the value is not a regex.

    :param object context: The click context object.
    :param object param: The click parameter definition.
    :param str value: The value for the --limit option.
    :return: The validated limit value. Either an integer or None for no limit.
    :rtype: int or None.
    :raises: click.BadParameter if the parameter is not valid.
    """
    #pylint: disable=unused-argument
    if value[0] == '/':
        raise click.BadParameter('{}: regex is not allowed.'.format(value))
    return value


def get_query_for_mutes(test_identifier):
    """ Create a points query from a test identifier.
     :param dict test_identifier: The project / variant / task / test and thread level values.
     :return: A query to get the points for this identifier.
    :rtype: dict
    """
    return test_identifier.copy()
