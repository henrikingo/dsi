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
from signal_processing.commands.helpers import stringify_json, get_query_for_points
from signal_processing.outliers.mute import get_identifier
from signal_processing.util.format_util import format_no_older_than, format_limit, \
    format_datetime, to_task_link, to_version_link, to_point_query

LOG = structlog.getLogger(__name__)

CONSECUTIVE_EXPIRED_LIMIT = 15
""" When there are more than 5 consecutive results, a mute is considered expired. """


def mute_expired(mute, points_collection):
    """
    Check if a mute has expired.

    A mute is expired if is was disabled  or has an expired field set to True.
    Otherwise if there are 14 or more contiguous newer points:
        * newer means that the order is greater (start should also be greater) OR
        * start is greater and order is less and there are no older points in between. That is,
        only count the newer points with less orders if there are no old points in between.

    :param dict mute: The mute document.
    :param pymongo.collection points_collection: The point collection
    :return: True if the mute has expired.
    """
    test_identifier = get_identifier(mute)

    if not mute['enabled'] or mute.get('expired', False):
        LOG.debug(
            'mute_expired: expired or disabled.', enabled=mute['enabled'], expired=mute['expired'])
        return True

    # find point matching the identifier
    after = get_query_for_points(test_identifier)
    del after['revision']
    after['order'] = {'$gte': mute['order']}

    points_after = list(points_collection.find(after))
    length = len(points_after)

    # If there are more than 15 points (including this one) after this one, then return expired.
    if length > CONSECUTIVE_EXPIRED_LIMIT:
        return True

    # Get 15 points less than this.
    before = get_query_for_points(test_identifier)
    del before['revision']
    before['order'] = {'$lt': mute['order']}

    points_before = list(
        points_collection.find(before).limit(15).sort([('order', pymongo.DESCENDING)]))
    start = mute['start']

    # Convert to True if point start is greater than mute start.
    # In this case the point was run after the mute.
    points_before_run_after = [point['start'] > start for point in points_before]

    # The index of the first False is the length.
    before_length = points_before_run_after.index(False)

    # Mute has expired if there were more than 15 consecutive, contiguous points.
    expired = length + before_length > 15
    LOG.debug('mute_expired', length=length, before_length=before_length, expired=expired)
    return expired


HUMAN_READABLE_TEMPLATE_STR = '''
[ {{ now() }} ] Running: `{{ command_line }}`
## {{ format_limit(limit) }} {{collection.name|replace("_", " ")|title}} {{ format_no_older_than(no_older_than) }}
## Task: `{{ _id.project }} {{ _id.variant }} {{ _id.task }} {{ _id.test}} {{ _id.thread_level }}`
{% for mute in mutes %}
- Order:        {{ mute.order }}
  Task Link:    <{{ mute|task_link(evergreen) }}>
  Version Link: <{{ mute|link(evergreen) }}>
  Revision:     `{{ mute.revision }}` / `{{ mute.order}}`
  Created:      `{{ mute.create_time }}`
  Last Updated: `{{ mute.last_updated_at|format_datetime }}`
  Start:        `{{ mute.start|format_datetime }}`
  End:          `{{ mute.end|format_datetime }}`
  Expired:      `{{ mute|expired(points_collection) }}`
  Enabled:      `{{ mute.enabled }}`
  Query:        `{{ mute|query(collection) }}`
  Identifier:   `{{ mute.revision }} {{ mute.project }} {{ mute.variant }} {{ mute.task }} {{ mute.test}} {{ mute.thread_level }}`
{% endfor -%}
'''
ENVIRONMENT = jinja2.Environment()

ENVIRONMENT.globals.update({
    'evergreen': evergreen_client.DEFAULT_EVERGREEN_URL,
    'command_line': " ".join([value if value else "''" for value in sys.argv]),
    'now': datetime.utcnow,
    'format_no_older_than': format_no_older_than,
    'format_limit': format_limit,
    'format_datetime': format_datetime,
    'task_link': to_task_link,
    'link': to_version_link,
    'expired': mute_expired,
})
ENVIRONMENT.filters.update({
    'link': to_version_link,
    'task_link': to_task_link,
    'query': to_point_query,
    'expired': mute_expired,
    'format_datetime': format_datetime,
})
HUMAN_READABLE_TEMPLATE = ENVIRONMENT.from_string(HUMAN_READABLE_TEMPLATE_STR)


def stream_human_readable(mutes, collection, points_collection, limit, no_older_than):
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
        _id=mutes['_id'],
        mutes=mutes['mutes'],
        collection=collection,
        points_collection=points_collection,
        limit=limit,
        no_older_than=no_older_than)


def create_pipeline(query, limit, no_older_than):
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
    pipeline.append({'$sort': {'order': pymongo.ASCENDING}})

    pipeline.extend([
        {
            '$group': {
                '_id': {
                    'project': '$project',
                    'variant': '$variant',
                    'task': '$task',
                    'test': '$test',
                    'thread_level': '$thread_level'
                },
                'create_time': {
                    '$max': '$create_time'
                },
                'mutes': {
                    '$push': '$$ROOT'
                }
            }
        },
        {
            '$project': {
                'project': '$_id.project',
                'variant': '$_id.variant',
                'task': '$_id.task',
                'test': '$_id.test',
                'thread_level': '$_id.thread_level',
                'mutes': 1,
            }
        },
    ])
    sort_order = {'$sort': OrderedDict([('create_time', pymongo.ASCENDING)])}

    pipeline.append(sort_order)

    if limit is not None:
        pipeline.append({'$limit': limit})
    return pipeline


def list_mutes(query, human_readable, limit, no_older_than, command_config):
    # pylint: disable=too-many-arguments, too-many-locals
    """
    List outliers mutes for tasks.

    :param dict() query: The criteria to match outliers.
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
        human_readable=human_readable,
        limit=limit,
        no_older_than=no_older_than,
        command_config=command_config)

    pipeline = create_pipeline(query, limit, no_older_than)
    collection = command_config.mute_outliers
    cursor = collection.aggregate(pipeline)

    if human_readable:
        for mutes in cursor:
            for line in stream_human_readable(mutes, collection, command_config.points, limit,
                                              no_older_than):
                print(line, end='')
    else:
        for i, point in enumerate(cursor):
            LOG.info(
                "list",
                i=i,
                collection=collection.name,
                point=stringify_json(point, compact=command_config.compact))
            print("//{}".format(i))
            print(stringify_json(point, compact=command_config.compact))