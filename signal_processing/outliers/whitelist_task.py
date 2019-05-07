# -*- coding: utf-8 -*-
"""
Functionality to manage whitelist.
"""
from __future__ import print_function

import re
import sys
from collections import OrderedDict
from datetime import datetime, timedelta

import jinja2

import pymongo
import structlog
from bson import ObjectId

from signal_processing.commands.helpers import stringify_json, get_whitelists
from signal_processing.util.format_util import format_no_older_than, format_limit

LOG = structlog.getLogger(__name__)

KEYS = ('revision', 'project', 'variant', 'task')
"""
A tuple containing the keys for a unique identifier for a task.
"""


def to_whitelist_query(whitelist, collection):
    """
    Jinja2 helper to get an atlas query for a whitelist.

    :param dict whitelist: The whitelist data.
    :param str collection: The collection name.
    :return: A query.
    """
    return "db.{collection}.find({{revision: '{revision}', project: '{project}', " \
           "variant: '{variant}', task: '{task}'}})".format(collection=collection.name,
                                                            revision=whitelist['revision'],
                                                            project=whitelist['project'],
                                                            variant=whitelist['variant'],
                                                            task=whitelist['task'])


ENVIRONMENT = jinja2.Environment()

ENVIRONMENT.globals.update({
    'command_line': " ".join([value if value else "''" for value in sys.argv]),
    'now': datetime.utcnow,
    'format_no_older_than': format_no_older_than,
    'format_limit': format_limit,
})
ENVIRONMENT.filters.update({
    'query': to_whitelist_query,
})
HUMAN_READABLE_TEMPLATE = ENVIRONMENT.from_string('''
[ {{ now() }} ] Running: `{{ command_line }}`
## {{ format_limit(limit) }} {{collection.name|replace("_", " ")|title}} {{ format_no_older_than(no_older_than) }}
{% for whitelist in whitelists %}
- ID:       `{{ loop.index }}`
  Revision: `{{ whitelist.revision }}`
  Order:    `{{ whitelist.order }}`
  Project:  `{{ whitelist.project }}`
  Variant:  `{{ whitelist.variant }}`
  Task:     `{{ whitelist.task }}`
  Query:    `{{ whitelist|query(collection) }}`
            `{{ whitelist.revision }} {{ whitelist.project }} {{ whitelist.variant}} {{ whitelist.task }}`
{% endfor %}
''')


def whitelist_identifier(point):
    """
    Get the identifier for a whitelist.
    :param dict point: The full data for the task revision.
    :return: TYhe unique identifier for a whitelist.
    :rtype: dict.
    """
    return {key: point[key] for key in KEYS}


def stream_human_readable(whitelists, collection, limit, no_older_than):
    """
    Stream the whitelists into an iterable human readable string.

    :param list(dict) whitelists: The whitelists data.
    :param object collection: The pymongo collection.
    :param int limit: The query limit.
    :param int no_older_than: The no_older_than value (days).
    :return: The human readable points.
    """
    return HUMAN_READABLE_TEMPLATE.stream(
        whitelists=whitelists, collection=collection, limit=limit, no_older_than=no_older_than)


def _create_object_id(days):
    """ Create an object id for days ago. """
    now = datetime.utcnow()
    start_date = datetime(now.year, now.month, now.day, tzinfo=now.tzinfo) - timedelta(days=days)
    return ObjectId.from_datetime(start_date)


def create_pipeline(query, limit, no_older_than, hide_wtdevelop):
    """
    Create an aggregation pipeline for matching, grouping and sorting change points. The pipeline
    consists of the following stages:
        1. Filter wtdevelop variants if *hide_wtdevelop* is True.
        1. Add the *query* as a match stage.
        1. Filter on _id if *no_older_than* was supplied.
        1. Sort by _id.
        1. Limit the results if limit param is not None.

    :param dict query: The query to match against.
    :param limit: The max number of points to match. None means all.
    :type limit: int or None.
    :param bool hide_wtdevelop: Should wtdevelop variants be excluded from the output.
    :param no_older_than: Exclude points with start fields older that this datetime.
                          None mean include all points.
    :type no_older_than: int or None
    :return: A list containing the aggregation pipeline.
    """
    pipeline = []

    if no_older_than is not None:
        pipeline.append({'$match': {'_id': {"$gte": _create_object_id(no_older_than)}}})

    if hide_wtdevelop:
        pipeline.append({'$match': {'variant': {'$not': re.compile('^wtdevelop')}}})

    pipeline.extend([{'$match': query}])
    sort_order = {'$sort': OrderedDict([('order', pymongo.DESCENDING)])}
    pipeline.append(sort_order)

    if limit is not None:
        pipeline.append({'$limit': limit})
    return pipeline


def list_whitelist(query, limit, no_older_than, human_readable, show_wtdevelop, command_config):
    # pylint: disable=too-many-arguments
    """
    List Whitelists.
    :param dict query: Find matching whitelists.
    :param int limit: Limit the number of whitelists found.
    :param int no_older_than: Only find whitelists newer than this.
    :param bool human_readable: Print as humna readable.
    :param bool show_wtdevelop: Show wt develop.
    :param CommandConfig command_config: Common configuration.
    """
    LOG.debug('list_whitelist', query=query, limit=limit, no_older_than=no_older_than)
    collection = command_config.whitelisted_outlier_tasks

    pipeline = create_pipeline(query, limit, no_older_than, not show_wtdevelop)
    cursor = collection.aggregate(pipeline)
    if human_readable:
        for line in stream_human_readable(cursor, collection, limit, no_older_than):
            print(line, end='')
    else:
        for i, whitelist in enumerate(cursor):
            LOG.info(
                "list",
                i=i,
                collection=collection.name,
                whitelist=stringify_json(whitelist, compact=command_config.compact))
            print("//{}".format(i))
            print(stringify_json(whitelist, compact=command_config.compact))


def add_whitelist(task_identifier, command_config):
    """
    Whitelist task revisions.
    :param dict task_identifier: A dict that is used to find matching task_revisions to whitelist.
    :param CommandConfig command_config: Common configuration.
    """
    LOG.debug('whitelist task', task_identifier=task_identifier)
    task_revisions = get_whitelists(task_identifier, command_config.points)
    collection = command_config.whitelisted_outlier_tasks

    requests = [
        pymongo.UpdateOne(
            whitelist_identifier(task_revision), {'$set': task_revision}, upsert=True)
        for task_revision in task_revisions
    ]
    try:
        if not command_config.dry_run:
            client = collection.database.client
            with client.start_session() as session:
                with session.start_transaction():
                    bulk_write_result = collection.bulk_write(requests, ordered=False)
            LOG.debug(
                "add_whitelist bulk_write",
                task_revisions=task_revisions,
                results=bulk_write_result.bulk_api_result)
        else:
            LOG.debug("add_whitelist bulk_write dryrun", requests=requests)
            print("add_whitelist dryrun {requests}".format(requests=requests))
    except Exception as e:
        # pylint: disable=no-member
        LOG.warn(
            'add_whitelist failed - rollback.',
            exc_info=True,
            details=e.details if hasattr(e, 'details') else str(e))
        raise


def remove_whitelist(task_identifier, command_config):
    """
    Remove a Whitelisting.
    :param dict task_identifier: A dict that is used to find matching task_revisions to whitelist.
    :param CommandConfig command_config: Common configuration.
    """
    LOG.debug('remove whitelist task', task_identifier=task_identifier)
    task_revisions = get_whitelists(task_identifier, command_config.points)
    collection = command_config.whitelisted_outlier_tasks

    requests = [
        pymongo.DeleteOne(whitelist_identifier(task_revision)) for task_revision in task_revisions
    ]
    try:
        if not command_config.dry_run:
            client = collection.database.client
            with client.start_session() as session:
                with session.start_transaction():
                    bulk_write_result = collection.bulk_write(requests, ordered=False)
            LOG.debug(
                "remove_whitelist bulk_write",
                task_revisions=task_revisions,
                results=bulk_write_result.bulk_api_result)
        else:
            LOG.debug("remove_whitelist bulk_write dryrun", requests=requests)
            print("remove_whitelist dryrun {requests}".format(requests=requests))

    except Exception as e:
        # pylint: disable=no-member
        LOG.warn(
            'remove_whitelist failed - rollback.',
            exc_info=True,
            details=e.details if hasattr(e, 'details') else str(e))
        raise
