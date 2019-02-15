# -*- coding: utf-8 -*-
"""
Functionality to list outliers.
"""
from __future__ import print_function

from collections import OrderedDict
from datetime import date, timedelta, datetime
import sys

import pymongo
import jinja2
import structlog

from analysis.evergreen import evergreen_client
from signal_processing.commands.helpers import stringify_json
from signal_processing.util.format_util import format_no_older_than, to_task_link, \
    to_version_link, format_limit, to_point_query

LOG = structlog.getLogger(__name__)

HUMAN_READABLE_TEMPLATE_STR = '''
[ {{ now() }} ] Running: `{{ command_line }}`
## {{ format_limit(limit) }} {{collection.name|replace("_", " ")|title}} {{ format_no_older_than(no_older_than) }}
## Task: `{{ _id.project }} {{ _id.variant }} {{ _id.task }} {{ _id.test}} {{ _id.thread_level }}`
{% for outlier in outliers %}
- Order:        {{ outlier.order_of_outlier }}
  Task Link:    <{{ outlier|task_link(evergreen) }}>
  Version Link: <{{ outlier|link(evergreen) }}>
  Revision:     `{{ outlier.revision }}` / `{{ outlier.order}}`
  Change Point: `{{ outlier.change_point_revision}}` / `{{ outlier.change_point_order}}`
  Query:        `{{ outlier|query(collection) }}`
  Type:         `{{ outlier.type }}`
  Identifier:   `{{ outlier.revision }} {{ outlier.project }} {{ outlier.variant }} {{ outlier.task }} {{ outlier.test}} {{ outlier.thread_level }}`
{% endfor -%}
'''
ENVIRONMENT = jinja2.Environment()

ENVIRONMENT.globals.update({
    'evergreen': evergreen_client.DEFAULT_EVERGREEN_URL,
    'command_line': " ".join([value if value else "''" for value in sys.argv]),
    'now': datetime.utcnow,
    'format_no_older_than': format_no_older_than,
    'format_limit': format_limit,
    'task_link': to_task_link,
    'link': to_version_link,
})
ENVIRONMENT.filters.update({
    'link': to_version_link,
    'task_link': to_task_link,
    'query': to_point_query,
})
HUMAN_READABLE_TEMPLATE = ENVIRONMENT.from_string(HUMAN_READABLE_TEMPLATE_STR)


def stream_human_readable(outliers, collection, limit, no_older_than):
    """
    Stream the outliers into an iterable human readable string.

    :param list(dict) outliers: The outliers data.
    :param object collection: The pymongo collection.
    :param limit: The max number of points to match. None means all.
    :type limit: int or None.
    :param no_older_than: Exclude points with start fields older that this datetime.
                          None mean include all points.
    :type no_older_than: int or None
    :return: The human readable outliers.
    """
    return HUMAN_READABLE_TEMPLATE.stream(
        _id=outliers['_id'],
        outliers=outliers['outliers'],
        collection=collection,
        limit=limit,
        no_older_than=no_older_than)


def create_pipeline(query, marked, types, limit, no_older_than):
    """
    Create an aggregation pipeline for matching, grouping and sorting outliers. The pipeline
    consists of the following stages:
        1. Filter on date if *no_older_than* was supplied.
        1. Add the *query* as a match stage.
        1. Add a match stage for types if types are supplied and not looking for marked outliers.
        1. Sort the outliers by order of outliers.
        1. Group outliers by
            * project.
            * variant.
            * task.
            * test.
            * thread_level.
            * change_point_revision.
            * change_point_order.
            * push each grouped item to outliers
        1. Project
            * project: '$_id.project',
            * change_point_revision: '$_id.change_point_revision',
            * change_point_order: '$_id.change_point_order',
            * outliers: 1,
        1. Sort by change_point_order (ascending).
        1. Limit the results if limit param is not None.
    :param dict query: The query to match against.
    :param bool marked: True if the pipeline is for marked outliers.
    :param list(str) types: The non-marked outlier types.
    :param limit: The max number of points to match. None means all.
    :type limit: int or None.
    :param no_older_than: Exclude points with start fields older that this datetime.
                          None mean include all points.
    :type no_older_than: int or None
    :return: A list containing the aggregation pipeline.
    """
    pipeline = []
    if no_older_than is not None:
        start_date = (date.today() - timedelta(days=no_older_than)).isoformat()
        pipeline.append({'$match': {'create_time': {"$gt": start_date}}})

    pipeline.append({'$match': query})
    if not marked and types:
        pipeline.append({'$match': {'type': {'$in': list(types)}}})
    pipeline.append({'$sort': {'order_of_outlier': pymongo.ASCENDING}})

    pipeline.extend([
        {
            '$group': {
                '_id': {
                    'project': '$project',
                    'variant': '$variant',
                    'task': '$task',
                    'test': '$test',
                    'thread_level': '$thread_level',
                    'change_point_revision': '$change_point_revision',
                    'change_point_order': '$change_point_order'
                },
                'outliers': {
                    '$push': '$$ROOT'
                }
            }
        },
        {
            '$project': {
                'project': '$_id.project',
                'change_point_revision': '$_id.change_point_revision',
                'change_point_order': '$_id.change_point_order',
                'outliers': 1,
            }
        },
    ])
    sort_order = {'$sort': OrderedDict([('change_point_order', pymongo.ASCENDING)])}

    pipeline.append(sort_order)

    if limit is not None:
        pipeline.append({'$limit': limit})
    return pipeline


def list_outliers(query, marked, types, human_readable, limit, no_older_than, command_config):
    # pylint: disable=too-many-arguments, too-many-locals
    """
    List matching outliers.
    :param dict() query: The criteria to match outliers.
    :param bool marked: Query the marked outliers collection if true otherwise outliers collection.
    :param list(str) types: The outlier types to display.
    :param bool human_readable: Print the output in human readable format.
    :param limit: Set a limit on the grouped output. None means no limit.
    :type limit: None, int
    :param no_older_than: Filter group failures older than this number of days.
    None means no filter.
    :type no_older_than: None, int
    :param CommandConfig command_config: Common configuration.
    :see SUSPICIOUS_TYPE
    :see DETECTED_TYPE
    """
    LOG.debug(
        'list outliers',
        query=query,
        marked=marked,
        types=types,
        human_readable=human_readable,
        limit=limit,
        no_older_than=no_older_than,
        command_config=command_config)

    pipeline = create_pipeline(query, marked, types, limit, no_older_than)
    if marked:
        collection = command_config.marked_outliers
    else:
        collection = command_config.outliers
    cursor = collection.aggregate(pipeline)

    if human_readable:
        for outliers in cursor:
            for line in stream_human_readable(outliers, collection, limit, no_older_than):
                print(line, end='')
    else:
        for i, point in enumerate(cursor):
            print("//{}".format(i))
            print(stringify_json(point, compact=command_config.compact))
