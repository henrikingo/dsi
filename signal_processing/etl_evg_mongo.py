"""
ETL history at project level into the `points` collection of the Mongo cluster.
"""
import datetime
import multiprocessing
import os
import re

import click
import pymongo
import structlog
import yaml

import etl_helpers
import signal_processing.commands.helpers as helpers
import signal_processing.commands.jobs as jobs
from analysis.evergreen import evergreen_client
from bin.common import log

DB = 'perf'
LOG = structlog.get_logger(__name__)
ALL_PROJECTS = [
    'sys-perf',
    'sys-perf-4.0',
    'sys-perf-3.6',
    'sys-perf-3.4',
    'performance',
    'performance-4.0',
    'performance-3.6',
    'performance-3.4',
    'mongo-longevity',
    'mongo-longevity-4.0',
    'mongo-longevity-3.6',
    'mongo-longevity-3.4'
]  # yapf: disable
"""
The list of all valid projects.
"""

DEFAULT_PROJECTS = [
    'sys-perf',
    'sys-perf-4.0',
    'sys-perf-3.6',
    'sys-perf-3.4',
    'performance',
    'performance-4.0',
    'performance-3.6',
    'performance-3.4'
]  # yapf: disable
"""
The list of default projects.
"""

IGNORE_TASKS_REGEX = re.compile('compile')

# May 2017 was the first month sys-perf results weren't totally noisy.
START_DATE = datetime.datetime(2017, 5, 15)


def _get_tasks(tasks):
    """
    Get the tasks in the latest build as a list of flat objects.

    :param dict tasks: The dictionary of task names and task objects for the variant returned from
    a query on the latest build of a given project.
    :rtype: list(dict).
    """
    # Add the task name to the task object.
    return [
        dict(task_object, task=task_name) for task_name, task_object in tasks.iteritems()
        if task_name in tasks and not IGNORE_TASKS_REGEX.match(task_name)
    ]


def _get_variant_tasks(history):
    """
    Get the task and variant combinations for the given project in the latest build as a list of
    flat objects.

    :param list history: The list of history objects returned from Evergreen.
    :rtype: list(dict).
    """
    if not history['versions']:
        return [{}]
    variants = history['versions'][0]['builds']
    # Add the variant name to the task object.
    return [
        dict(task_object, variant=variant_name)
        for variant_name, variant_object in variants.iteritems()
        if variant_name in variants for task_object in _get_tasks(variant_object['tasks'])
    ]


def _get_project_variant_tasks(evg_client, project):
    """
    Get the task, variant, and project combinations in the latest build as a list of flat objects.
    These are the entry points for scavenging history for all tasks.

    :param evergreen_client.Client evg_client: The client connection to Evergreen.
    :param str project: The project to fetch history from.
    :rtype: list(dict).
    """
    # TODO: PERF-1589: Copy all data not just tasks in most recent build.

    history = evg_client.query_project_history(project)

    # Get the variant / task combinations for the history
    # For each task and variant combination the project name and version_id are added to the task
    # object representing that task and variant combinations, resulting in a flattened task
    # object for the project.
    return [
        dict(task_object, project=project, version_id=history['versions'][0]['version_id'])
        for task_object in _get_variant_tasks(history) if task_object
    ]


def _get_last_version_id(mongo_uri, variant, task_name, project):
    """
    Get the version_id of the newest point from the database for the project, task and variant.
    The ETL can then use  this value to query evergreen for all data newer than this version id.

    :param str mongo_uri: The uri to connect to the cluster.
    :param str variant: The name of the build variant.
    :param str task_name: The name of the task to query.
    :param str project: The name of the project to query.
    :rtype: str.
    """
    # pylint: disable=invalid-name
    db = pymongo.MongoClient(mongo_uri).get_database()
    last_version_id = None
    results = list(
        db.points.find({
            'project': project,
            'task': task_name,
            'variant': variant
        }, {
            'version_id': True
        }).sort('order', -1).limit(1))
    if results:
        last_version_id = results[0]['version_id']
    return last_version_id


def _etl_single_task(evg_client, mongo_uri, task):
    """
    Determines the most recent point existing in the mongodb, and then fetches all newer points
    from Evergreen and loads them into the mongodb. For each task, the points are loaded in order
    from oldest to newest so that the function is restartable.

    :param str evg_client: The Evergreen configuration file.
    :param str mongo_uri: The uri to connect to the cluster.
    :param dict task: The task to load.
    """
    # pylint: disable=too-many-locals
    results = []
    fetch_more = True
    seen_task_ids = set()
    project = task['project']
    task_name = task['task']
    task_id = task['task_id']
    variant = task['variant']
    if task_name == 'compile':
        return
    last_version_id = _get_last_version_id(mongo_uri, variant, task_name, project)

    LOG.info(
        'Start copying data for task.',
        variant=variant,
        task_name=task_name,
        last_version_id=last_version_id,
        start_date=START_DATE)
    # Continue fetching history from Evergreen until either there is no more history or we reach
    # a set stopping point.
    while fetch_more:
        LOG.info(
            'Fetch next batch of history for task',
            variant=variant,
            task_name=task_name,
            start_task_id=task_id)
        result_history = evg_client.query_mongo_perf_task_history(task_name, task_id)
        if not isinstance(result_history, list):
            break
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

    LOG.info(
        'Done extracting task, now inserting into mongodb.',
        variant=variant,
        task_name=task_name,
        len=len(results))
    # Add the results to the mongodb from oldest to newest. This way if the process is
    # interrupted, the next run will pick up from where it left off without leaving a gap of
    # information.
    results.reverse()
    for result in results:
        etl_helpers.load(result, mongo_uri)
    return task


def _get_task_identifiers(evg_client, projects, progressbar, pool_size=1):
    """
    Get a list of task identifiers from evergreen for each of the projects.

    :param str evg_client: The evergreen client instance.
    :param list projects: The list of projects to load.
    :param bool progressbar: Render a progressbar.
    :param int pool_size: The size of the process pool. 1 implies runs everything inline.
    """
    # pylint: disable=too-many-locals
    task_identifiers = []
    label = 'loading tasks'
    LOG.info(label, projects=projects)

    max_length = max(len(project) for project in projects + [label])

    # Add 2 so that there is some whitespace between the label and progress bar.
    label = label.ljust(max_length + 2)
    job_list = [
        jobs.Job(_get_project_variant_tasks, arguments=(evg_client, project), identifier=project)
        for project in projects
    ]

    bar_template, show_item = helpers.query_terminal_for_bar()
    completed_jobs = jobs.process_jobs(
        job_list,
        pool_size=pool_size,
        label=label,
        progressbar=progressbar,
        bar_template=bar_template,
        show_item=show_item)
    for job in completed_jobs:
        if job.exception is not None:
            raise job.exception
        task_identifiers.extend(job.result)
    return task_identifiers


def _etl_evg_mongo(evg_client, mongo_uri, projects, progressbar, pool_size=1):
    """
    Determines the most recent point existing in the mongodb, and then fetches all newer points from
    Evergreen and loads them into the mongodb. For each task, the points are loaded in order from
    oldest to newest so that the function is restartable.

    :param str evg_client: The evergreen client instance.
    :param str mongo_uri: The uri to connect to the cluster.
    :param list projects: The list of projects to load.
    :param bool progressbar: Render a progressbar.
    :param int pool_size: The size of the process pool. 1 implies runs everything inline.
    """
    # pylint: disable=too-many-locals
    task_identifiers = _get_task_identifiers(evg_client, projects, progressbar, pool_size=pool_size)

    LOG.info('loaded tasks', tasks=len(task_identifiers))
    LOG.debug('loaded tasks', tasks=task_identifiers)
    label = 'loading data'

    job_list = [
        jobs.Job(_etl_single_task, arguments=(evg_client, mongo_uri, task), identifier=task)
        for task in task_identifiers
    ]

    bar_template, show_item = helpers.query_terminal_for_bar()
    completed_jobs = jobs.process_jobs(
        job_list,
        pool_size=pool_size,
        label=label,
        progressbar=progressbar,
        bar_template=bar_template,
        show_item=show_item,
        key='task')
    jobs_with_exceptions = [job for job in completed_jobs if job.exception is not None]
    return jobs_with_exceptions


@click.command(context_settings=dict(help_option_names=['-h', '--help']))
@click.pass_context
@click.option(
    '--evergreen-config',
    default='~/.evergreen.yml',
    help='Evergreen config file (url and auth tokens)')
@click.option(
    '--mongo-uri',
    default='mongodb://localhost:27017/' + DB,
    help='MongoDB connection string. (A MongoDB is required!)')
@click.option('-v', '-d', 'verbose', count=True, help='Control the verbosity.')
@click.option(
    '-l',
    '--logfile',
    default='etl_evg_mongo.log',
    help='The log file location. Use /dev/stdout (or stderr) for console.')
@click.option('--progressbar/--no-progressbar', default=False)
@click.option('--all', 'all_projects', default=False, is_flag=True)
@click.option(
    '--pool-size',
    default=max(multiprocessing.cpu_count() - 1, 1),
    help='Set the process pool size. The default is the number of cores -1.')
@click.option(
    '--project',
    'projects',
    type=click.Choice(ALL_PROJECTS),
    default=DEFAULT_PROJECTS,
    required=False,
    multiple=True,
    help='The list of projects to loads. Defaults to {}'.format(DEFAULT_PROJECTS))
def etl(context, evergreen_config, mongo_uri, verbose, logfile, progressbar, all_projects,
        pool_size, projects):
    # pylint: disable=too-many-arguments
    """
Load the history from Evergreen into the Mongo Atlas cluster.

The options are listed below, but a list of projects is the main configurable.

\b
Examples:
    # Load all the points for the default projects
    $> MONGO_URI=mongodb:...
    $> etl-evg-mongo --mongo-uri ${MONGO_URI}
\b
    # Load all the points for the sys-perf project
    $> MONGO_URI=mongodb:...
    $> etl-evg-mongo --mongo-uri ${MONGO_URI} --project sys-perf
\b
    # Load all the points for the sys-perf and performance projects
    $> MONGO_URI=mongodb:...
    $> etl-evg-mongo --mongo-uri ${MONGO_URI}  --project sys-perf --project performance
\b
    # Load all the points with a progress bar
    $> MONGO_URI=mongodb:...
    $> etl-evg-mongo --mongo-uri ${MONGO_URI} --project sys-perf --project performance\
       --progressbar
\b
    # Load all the points, set log level to debug
    $> MONGO_URI=mongodb:...
    $> etl-evg-mongo --mongo-uri ${MONGO_URI} -v
\b
    # Load all the points (default projects), log to console
    $> MONGO_URI=mongodb:...
    $> etl-evg-mongo --mongo-uri ${MONGO_URI} -l /dev/stdout
\b
    # Load all the points from all projects
    $> MONGO_URI=mongodb:...
    $> etl-evg-mongo --mongo-uri ${MONGO_URI} --all --progress-bar
"""

    log.setup_logging(True if verbose > 0 else False, logfile)
    path = os.path.expanduser(evergreen_config)
    with open(path) as config_file:
        evg_client = evergreen_client.Client(yaml.load(config_file))

    if all_projects:
        projects = ALL_PROJECTS
    if not projects:
        projects = DEFAULT_PROJECTS

    LOG.debug(
        'downloading data from evergreen',
        mongo_uri=etl_helpers.redact_url(mongo_uri),
        projects=projects)

    jobs_with_exceptions = _etl_evg_mongo(
        evg_client, mongo_uri, list(projects), progressbar, pool_size=pool_size)

    jobs.handle_exceptions(context, jobs_with_exceptions, logfile)
