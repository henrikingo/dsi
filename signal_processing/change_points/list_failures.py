# -*- coding: utf-8 -*-
"""
Functionality to list change points.
"""
from __future__ import print_function

from collections import defaultdict
from datetime import date, timedelta, datetime
import sys

from dateutil import parser as date_parser
import jinja2
import structlog

from analysis.evergreen import evergreen_client
from signal_processing.commands.helpers import stringify_json

LOG = structlog.getLogger(__name__)

DEFAULT_EVERGREEN_URL = 'https://evergreen.mongodb.com'
"""The default Evergreen URL."""

HUMAN_READABLE_TEMPLATE_STR = '''
[ {{ now() }} ] Running: `{{ command_line }}`
##
{% for grouping in tasks %}
- ID:      `{{ loop.index }}`
  Name:    `{{ grouping.name }}`
  Time:    `{{ grouping.start_time }}`
  Project: <{{ grouping.tasks[0]|link(evergreen) }}>
{%- for task in grouping.tasks|sort(attribute='start_time', reverse=True) %}
   - Link:     <{{ task|task_link(evergreen) }}>
     Revision: `{{ task.revision }}`
     Start:    `{{ task.start_time }}`
     Status:   `{{ task.status }}`
     Type:     `{{ task.status_details.type|title }} Failure{{ ' Timed Out' if task.status_details.timed_out }}`
     Desc:     `{{ task.status_details.desc }}`
{% endfor -%}
{% endfor -%}
'''


def to_link(task, evergreen):
    """
    Get the evergreen project link for this task. This function
    is passed to the Jinja2 environment.

    :param dict task: The task data.
    :return: A string url.
    """
    return "{evergreen}/waterfall/{project_id}".format(
        project_id=task['project_id'], evergreen=evergreen)


def to_task_link(task, evergreen):
    """
    Get the evergreen link for this task. This function is passed to
    the Jinja2 environment.

    :param dict test: The test data.
    :return: A string url.
    """
    return "{evergreen}/task/{task_id}".format(task_id=task['task_id'], evergreen=evergreen)


def group_sort(tasks, reverse=False):
    """
    Group tasks by task_id (excluding the revision and time) which is
    equivalent to grouping by 'project', 'variant', 'task', and then sort by
    start_time.

    :param list(dict) tasks: The list of tasks.
    :param bool reverse: The default sort is start_time descending. Set reverse
    to True for ascending order.
    :return: The list of sorted tasks.
    """
    groups = defaultdict(lambda: {'name': '', 'start_time': None, 'tasks': []})

    # loop through each task and group by
    # the task_id (less the revision and date):
    #   set the name to the task_id (less the revision and date)
    #   set the start_time to the current task start_time if it is
    #    greater than the current value
    #   add this task to the list of tasks
    for task in tasks:
        task_id = task['task_id']
        revision = task['revision']
        pos = task_id.find(revision) - 1
        identifier = task_id[:pos]
        group = groups[identifier]
        group['tasks'].append(task)
        group['name'] = identifier
        start = date_parser.parse(task['start_time']).replace(tzinfo=None)
        if group['start_time'] is None or start > date_parser.parse(
                group['start_time']).replace(tzinfo=None):
            group['start_time'] = task['start_time']

    # Sort the grouped values by start_time
    sorted_tasks = sorted(
        groups.values(),
        key=lambda task: date_parser.parse(task['start_time']).replace(tzinfo=None),
        reverse=not reverse)
    return sorted_tasks


ENVIRONMENT = jinja2.Environment()
ENVIRONMENT.globals.update({
    'evergreen': DEFAULT_EVERGREEN_URL,
    'command_line': " ".join([value if value else "''" for value in sys.argv]),
    'now': datetime.utcnow,
    'task_link': to_task_link,
    'link': to_link,
})
ENVIRONMENT.filters.update({'link': to_link, 'task_link': to_task_link, 'group_sort': group_sort})
HUMAN_READABLE_TEMPLATE = ENVIRONMENT.from_string(HUMAN_READABLE_TEMPLATE_STR)


def stream_human_readable(tasks):
    """
    Stream the tasks into an iterable human readable string.

    :param list(dict) tasks: The task status data.
    :return: The human readable tasks.
    """
    return HUMAN_READABLE_TEMPLATE.stream(tasks=tasks)


def list_failures(project, show_wtdevelop, show_patches, human_readable, limit, no_older_than,
                  evg_client, command_config):
    # pylint: disable=too-many-arguments, too-many-locals
    """
    List all failures for a given project.

    :param str project: The performance project name.
    :param bool show_wtdevelop: Filter wtdevelop tasks when True.
    :param bool show_patches: Filter patch tasks when True.
    :param bool human_readable: Print the output in human readable format.
    :param limit: Set a limit on the grouped output. None means no limit.
    :type limit: None, int
    :param no_older_than: Filter group failures older than this number of days.
    None means no filter.
    :type no_older_than: None, int
    :param bool evg_client: Print the output in human readable format.
    :param evergreen_client.Client evg_client: The evergreen client instance.
    :param CommandConfig command_config: Common configuration.
    """
    LOG.debug('list failures')

    failures = evg_client.get_project_tasks(project, statuses=[evergreen_client.TASK_STATUS_FAILED])
    if not failures:
        LOG.info('list_failures no results')
        return

    failure_groups = group_sort(failures)

    if not show_patches:
        # TODO EVG-5462: update to use a field (is_patch?) if it becomes available.
        failure_groups = [
            result for result in failure_groups
            if '_patch_' + result['tasks'][0]['revision'] not in result['tasks'][0]['task_id']
        ]

    if not show_wtdevelop:
        failure_groups = [
            result for result in failure_groups
            if 'wtdevelop' not in result['tasks'][0]['build_variant']
        ]

    if not failure_groups:
        LOG.info('list_failures no failed tests')
        return

    if limit:
        failure_groups = failure_groups[:limit]

    if no_older_than is not None:
        start_date = date.today() - timedelta(days=no_older_than)
        start_time = datetime.combine(start_date, datetime.min.time())
        failure_groups = [
            failure for failure in failure_groups
            if date_parser.parse(failure['start_time']).replace(tzinfo=None) > start_time
        ]

    if human_readable:
        for line in stream_human_readable(failure_groups):
            print(line, end='')
    else:

        for i, failure in enumerate(failure_groups):
            print("//{}".format(i))
            print(stringify_json(failure, compact=command_config.compact))
