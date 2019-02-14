# -*- coding: utf-8 -*-
"""
Common Jinja Template helpers.
"""
from __future__ import print_function

import jinja2
import math
from datetime import datetime

import structlog

from signal_processing.commands.helpers import stringify_json

LOG = structlog.getLogger(__name__)


def format_no_older_than(no_older_than):
    """
    Jinja2 helper to format no_older_than.

    :param no_older_than: The format_no_older_than value.
    :type no_older_than: int or None.
    :return: A string representing the no older than value.
    """
    if no_older_than is None:
        return 'All'
    return "Last {} days".format(no_older_than)


def format_limit(limit):
    """
    Jinja2 helper to format limit.

    :param limit: The limit value.
    :type limit: int or None.
    :return: A string representing the limit value.
    """
    if limit is None:
        return 'All'
    return "UpTo {}".format(limit)


def to_version_link(test, evergreen):
    """
    Jinja2 helper to get an evergreen link for a test.

    :param dict test: The test data.
    :param str evergreen: The evergreen base url.
    :return: A string url.
    """
    return "{evergreen}/version/{version_id}".format(
        version_id=test['version_id'], evergreen=evergreen)


def to_project_link(task, evergreen):
    """
    Get the evergreen project link for this task. This function
    is passed to the Jinja2 environment.

    :param dict task: The task data.
    :return: A string url.
    """
    return "{evergreen}/waterfall/{project_id}".format(
        project_id=task['project_id'], evergreen=evergreen)


def to_task_link(test, evergreen):
    """
    Jinja2 helper to get an evergreen link for a task.

    :param dict test: The test data.
    :param str evergreen: The evergreen base url.
    :return: A string url.
    """
    return "{evergreen}/task/{task_id}".format(task_id=test['task_id'], evergreen=evergreen)


def to_point_query(test, collection):
    """
    Jinja2 helper to get an atlas query for a test.

    :param dict test: The test data.
    :param pymongo.collection collection: The collection.
    :return: A query.
    """
    template = "db.{collection}.find({{project: '{project}', variant: '{variant}', " \
               "task: '{task}', test: '{test}', thread_level: '{thread_level}', " \
               "revision: '{revision}'}})"
    return template.format(
        collection=collection.name,
        project=test['project'],
        variant=test['variant'],
        task=test['task'],
        test=test['test'],
        thread_level=test['thread_level'],
        revision=test['revision'])


def to_change_point_query(test, collection):
    """
    Jinja2 helper to get an atlas query for a test.

    :param dict test: The test data.
    :return: A query.
    """
    return "db.{collection}.find({{project: '{project}', "\
           "suspect_revision: '{suspect_revision}'}})".format(
               collection=collection.name,
               project=test['project'],
               suspect_revision=test['suspect_revision'])


def format_datetime(value):
    """ convert value to an isoformat timestamp.

    :param value: The value to convert to a timestamp. Floats or ints are assumed to be utc.
    datetime values are converted to the equivalent UTC time before formatting. microseconds are
    always removed.
    :type value: float or int or datetime.
    :return: A string representing the datetime.
    """
    if isinstance(value, (int, float)):
        value = datetime.utcfromtimestamp(value)
    else:
        value = value.replace(tzinfo=None)
    return value.replace(microsecond=0).isoformat() + 'Z'


def magnitude_to_percent(magnitude, format_string='%+3.0f%%'):
    """
    Jinja2 helper to convert magnitude to percentage change.

    :param magnitude: The magnitude value is only valid as a float.
    :type magnitude: float or jinja2.runtime.Undefined or None.
    :return: A string representing the percentage change.
    """
    if magnitude is None or isinstance(magnitude, jinja2.runtime.Undefined):
        return 'Nan'
    return format_string % (math.exp(magnitude) * 100.0 - 100.0)
