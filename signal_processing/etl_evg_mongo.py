"""
ETL history at project level into the `points` collection of the Mongo cluster.
"""
import argparse
import datetime
import logging
import os
import yaml

import pymongo

import etl_helpers
from analysis.evergreen import evergreen_client
from bin.common import log

DB = 'perf'
LOG = logging.getLogger(__name__)
DEFAULT_HISTORY_CONFIG = {'sys-perf': None, 'performance': None}
# This is an arbitrary date and subject to change.
START_DATE = datetime.datetime(2017, 5, 15)


def _get_tasks(project, variant_name, tasks, history_config):
    """
    Get the tasks in the latest build for the given variant and project as a list of flat objects.
    Omit any tasks that are excluded by `history_config`.

    :param str variant_name: The name of the build variant.
    :param dict tasks: The dictionary of task names and task objects for the variant returned from a
    query on the latest build of a given project.
    :param dict history_config: The configuration dictionary specifying which
    test/task/variant/project(s) to fetch history from.
    :rtype: list(dict).
    """
    if history_config[project] and history_config[project][variant_name]:
        config_tasks = history_config[project][variant_name]
    else:
        config_tasks = tasks
    # Add the task name to the task object.
    return [
        dict(task_object, task=task_name) for task_name, task_object in tasks.iteritems()
        if task_name in config_tasks
    ]


def _get_variant_tasks(project, history, history_config):
    """
    Get the task and variant combinations for the given project in the latest build as a list of
    flat objects. Omit any variants that are excluded by `history_config`.

    :param str project: The name of the project to query.
    :param list history: The list of history objects returned from Evergreen.
    :param dict history_config: The configuration dictionary specifying which
    test/task/variant/project(s) to fetch history from.
    :rtype: list(dict).
    """
    variants = history['versions'][0]['builds']
    config_variants = history_config[project] if history_config[project] else variants
    # Add the variant name to the task object.
    return [
        dict(task_object, variant=variant_name)
        for variant_name, variant_object in variants.iteritems()
        if variant_name in config_variants for task_object in _get_tasks(
            project, variant_name, variant_object['tasks'], history_config)
    ]


def _get_project_variant_tasks(evg_client, history_config):
    """
    Get the task, variant, and project combinations in the latest build as a list of flat objects.
    These are the entry points for scavenging history for all tasks. Omit any projects that
    are exluded by `history_config`.

    :param evergreen_client.Client evg_client: The client connection to Evergreen.
    :param dict history_config: The configuration dictionary specifying which
    test/task/variant/project(s) to fetch history from.
    :rtype: list(dict).
    """
    # TODO: PERF-1589: Copy all data not just tasks in most recent build.

    # The outer loop gets the project names that will be loaded, the inner loops gets all the task
    # and variant combinations in the latest build for each project. For each task and variant
    # combination the project name and version_id are added to the task object representing that
    # task and variant combination, resulting in a flattened task object for each task, variant, and
    # project combination.
    return [
        dict(task_object, project=project, version_id=history['versions'][0]['version_id'])
        for project, history in {
            project: evg_client.query_project_history(project)
            for project in DEFAULT_HISTORY_CONFIG.iterkeys() if project in history_config
        }.iteritems() for task_object in _get_variant_tasks(project, history, history_config)
    ]


def _get_last_version_id(mongo_uri, variant, task_name):
    """
    For `task_name`, see what is the most recent version_id we already have in the `points`
    collection. From that point forward we will continue ETLing.

    :param str mongo_uri: The uri to connect to the cluster.
    :param str variant: The name of the build variant.
    :param str task_name: The name of the task to query.
    :rtype: str.
    """
    # pylint: disable=invalid-name
    db = pymongo.MongoClient(mongo_uri).get_database()
    last_version_id = None
    iterator = db.points.find({
        'project': {
            '$in': [project for project in DEFAULT_HISTORY_CONFIG.iterkeys()]
        },
        'task': task_name,
        'variant': variant
    }, {
        'version_id': True
    }).sort('order', -1).limit(1)
    if iterator:
        try:
            doc = iterator.next()
            last_version_id = doc['version_id']
        except StopIteration:
            pass
    return last_version_id


def _etl_evg_mongo(evg_client, mongo_uri, history_config=None):
    """
    Determines the most recent point existing in the mongodb, and then fetches all newer points from
    Evergreen and loads them into the mongodb. For each task, the points are loaded in order from
    oldest to newest so that the function is restartable.

    :param evergreen_client.Client evg_client: The client connection to Evergreen.
    :param str mongo_uri: The uri to connect to the cluster.
    :param history_config: The configuration dictionary specifying which
    test/task/variant/project(s) to fetch history from. Note that omitting the history_config
    paramater defaults to fetching history for all test/task/variant/projects.
    :type history_config: dict, None.
    """
    # pylint: disable=too-many-locals
    history_config = history_config if history_config else DEFAULT_HISTORY_CONFIG
    project_variant_tasks = _get_project_variant_tasks(evg_client, history_config)
    for task in project_variant_tasks:
        results = []
        fetch_more = True
        seen_task_ids = set()
        task_name = task['task']
        task_id = task['task_id']
        variant = task['variant']
        project = task['project']
        if task_name == 'compile':
            continue
        try:
            tests = set([test for test in history_config[project][variant][task_name]])
        except (KeyError, TypeError):
            tests = None
        last_version_id = _get_last_version_id(mongo_uri, variant, task_name)

        LOG.info('Start copying data for %s/%s, starting from %s / %s', variant, task_name,
                 last_version_id, START_DATE)
        # Continue fetching history from Evergreen until either there is no more history or we reach
        # a set stopping point.
        while fetch_more:
            LOG.info('Fetch next batch of history for %s/%s, starting with %s', variant, task_name,
                     task_id)
            result_history = evg_client.query_mongo_perf_task_history(task_name, task_id)
            if not isinstance(result_history, list):
                continue
            # Search the history from newest to oldest.
            result_history.reverse()
            for result in result_history:
                # Evergreen returns results both earlier and later than the specified task_id, so we
                # need to ensure that we are only storing each result once.
                if result['task_id'] in seen_task_ids:
                    # If we do not see anymore new task ids, need to stop fetching history from
                    # Evergreen to avoid an infinite loop.
                    fetch_more = False
                    continue
                if result['version_id'] == last_version_id or \
                   result['create_time'] <= START_DATE.isoformat():
                    fetch_more = False
                    break
                fetch_more = True
                seen_task_ids.add(result['task_id'])
                task_id = result['task_id']
                results.append(result)

        LOG.info('Done extracting %s/%s, now inserting into mongodb.', variant, task_name)
        # Add the results to the mongodb from oldest to newest. This way if the process is
        # interrupted, the next run will pick up from where it left off without leaving a gap of
        # information.
        results.reverse()
        for result in results:
            etl_helpers.load(result, mongo_uri, tests)


def _parse_command_line():
    """
    Parse the command line options.
    """
    parser = argparse.ArgumentParser(description='Specify one Evergreen and one MongoDB please.')
    parser.add_argument(
        '--evergreen-config',
        default='~/.evergreen.yml',
        help='Evergreen config file (url and auth tokens)')
    parser.add_argument(
        '--mongo-uri',
        default='mongodb://localhost:27017/' + DB,
        help='MongoDB connection string. (A MongoDB is required!)')
    parser.add_argument('-d', '--debug', action='store_true', help='Enable debug output')
    args = parser.parse_args()
    return args


def etl():
    """
    Get the command line arguments and load the history from Evergreen into the Mongo cluster.
    """
    args = _parse_command_line()
    log.setup_logging(args.debug, None)
    path = os.path.expanduser(args.evergreen_config)
    with open(path) as config_file:
        evg_client = evergreen_client.Client(yaml.load(config_file))
    _etl_evg_mongo(evg_client, args.mongo_uri)
