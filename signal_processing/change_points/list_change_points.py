# -*- coding: utf-8 -*-
"""
Functionality to list change points.
"""
from __future__ import print_function

import operator
from collections import OrderedDict
from datetime import date, datetime, timedelta
import math
import re
import sys

import jinja2
import pymongo
import structlog

from analysis.evergreen import evergreen_client
from signal_processing.commands.helpers import filter_excludes, stringify_json
from signal_processing.util.format_util import format_no_older_than, format_limit, \
    magnitude_to_percent, to_task_link, to_version_link, to_change_point_query

LOG = structlog.getLogger(__name__)

CHANGE_POINT_TYPE_PROCESSED = 'processed'
CHANGE_POINT_TYPE_UNPROCESSED = 'unprocessed'
CHANGE_POINT_TYPE_RAW = 'raw'
VALID_CHANGE_POINT_TYPES = [
    CHANGE_POINT_TYPE_PROCESSED, CHANGE_POINT_TYPE_UNPROCESSED, CHANGE_POINT_TYPE_RAW
]


def group_sort(tests, reverse=False):
    """
    Sort the tests by 'variant', 'task', 'test', 'thread_level' to logically
    group them.

    :param list(dict) tests: The list of tests.
    :param bool reverse: Reverse the order.
    :return: The list of sorted tests.
    """
    tests.sort(reverse=reverse, key=operator.itemgetter('variant', 'task', 'test', 'thread_level'))
    return tests


HUMAN_READABLE_TEMPLATE_STR = '''
[ {{ now() }} ] Running: `{{ command_line }}`
## {{ format_limit(limit) }} {{collection.name|replace("_", " ")|title}} {{ format_no_older_than(no_older_than) }}
{% for point in points %}
- ID:       `{{ loop.index }}`
  Link:     <{{ point|link(evergreen) }}>
  Project:  `{{ point.project }}`
  Suspect Revision: `{{ point.suspect_revision }}`
  Query:    `{{ point|query(collection) }}`
  Start:     `{{ point.start }}`
  Tests: {{ point.change_points|length }}({{ magnitude_to_percent(point.min_magnitude, '%+5.2f%%') }})
{% for test in point.change_points|group_sort %}
  - {{ magnitude_to_percent(test.magnitude) }} `{{ point.suspect_revision }} {{ point.project }} {{ test.variant }} {{ test.task }} {{ test.test }} {{ test.thread_level }}` {{ test.processed_type }}
    {%- if test.task_id %}
    {{'<%s>'|format(task_link(test, evergreen)) }}
    {%- endif %}
{%- endfor %}
{% endfor %}
'''
ENVIRONMENT = jinja2.Environment()

ENVIRONMENT.globals.update({
    'evergreen': evergreen_client.DEFAULT_EVERGREEN_URL,
    'command_line': " ".join([value if value else "''" for value in sys.argv]),
    'now': datetime.utcnow,
    'format_no_older_than': format_no_older_than,
    'format_limit': format_limit,
    'isnan': math.isnan,
    'magnitude_to_percent': magnitude_to_percent,
    'task_link': to_task_link,
    'link': to_version_link,
})
ENVIRONMENT.filters.update({
    'link': to_version_link,
    'task_link': to_task_link,
    'query': to_change_point_query,
    'group_sort': group_sort
})
HUMAN_READABLE_TEMPLATE = ENVIRONMENT.from_string(HUMAN_READABLE_TEMPLATE_STR)


def create_pipeline(query, limit, hide_canaries, hide_wtdevelop, no_older_than):
    """
    Create an aggregation pipeline for matching, grouping and sorting change points. The pipeline
    consists of the following stages:
        1. Filter canary tests if *hide_canaries* is True.
        1. Filter wtdevelop variants if *hide_wtdevelop* is True.
        1. Create a start field.
        1. Add the *query* as a match stage.
        1. Filter on date if *no_older_than* was supplied.
        1. Add new previous and next mean fields and ensure sensible defaults if next
        or previous statistics are missing. This is unlikely but possible.
        1. Group the change points by project and revision.
            * Get newest create time.
            * Get newest start.
            * Get max magnitude.
            * Get min magnitude.
            * All change points.
        1. Project the fields listed above.
        1. Sort.
            * Sort by min_magnitude (ascending).
        1. Limit the results if limit param is not None.

    :param dict query: The query to match against.
    :param limit: The max number of points to match. None means all.
    :type limit: int or None.
    :param bool show_canaries: Should canaries tests be excluded from the output.
    :param bool hide_wtdevelop: Should wtdevelop variants be excluded from the output.
    :param bool hide_wtdevelop: Should wtdevelop variants be excluded from the output.
    :param no_older_than: Exclude points with start fields older that this datetime.
                          None mean include all points.
    :type no_older_than: int or None
    :return: A list containing the aggregation pipeline.
    """
    pipeline = []
    if no_older_than is not None:
        start_date = (date.today() - timedelta(days=no_older_than)).isoformat()
        pipeline.append({'$match': {'create_time': {"$gt": start_date}}})
    if hide_canaries:
        pipeline.append({
            '$match': {
                'test': {
                    '$not': re.compile('^(canary_|fio_|NetworkBandwidth)')
                }
            }
        })

    if hide_wtdevelop:
        pipeline.append({'$match': {'variant': {'$not': re.compile('^wtdevelop')}}})

    pipeline.extend([
        # TODO: consider removing the following after PERF-1664
        {
            '$addFields': {
                'start': {
                    '$ifNull': ["$start", {
                        '$dateFromString': {
                            'dateString': '$create_time'
                        }
                    }]
                }
            }
        },
        {
            '$match': query
        }
    ])

    pipeline.extend([
        {
            '$group': {
                '_id': {
                    'project': '$project',
                    'suspect_revision': '$suspect_revision'
                },
                'create_time': {
                    '$max': '$create_time'
                },
                'start': {
                    '$max': '$start'
                },
                'magnitude': {
                    '$max': '$magnitude'
                },
                'min_magnitude': {
                    '$min': '$magnitude'
                },
                'change_points': {
                    '$push': '$$ROOT'
                },
                'version_id': {
                    '$first': '$$ROOT.version_id'
                }
            }
        },
        {
            '$project': {
                'project': '$_id.project',
                'suspect_revision': '$_id.suspect_revision',
                'version_id': '$version_id',
                'change_points': 1,
                'start': 1,
                'create_time': 1,
                'magnitude': 1,
                'min_magnitude': 1,
            }
        },
    ])
    sort_order = {'$sort': OrderedDict([('min_magnitude', pymongo.ASCENDING)])}

    pipeline.append(sort_order)

    if limit is not None:
        pipeline.append({'$limit': limit})
    return pipeline


def stream_human_readable(points, collection, limit, no_older_than):
    """
    Stream the points into an iterable human readable string.

    :param list(dict) points: The change points data.
    :param object collection: The pymongo collection.
    :return: The human readable points.
    """
    return HUMAN_READABLE_TEMPLATE.stream(
        points=points, collection=collection, limit=limit, no_older_than=no_older_than)


def map_collection(change_point_type, command_config):
    """
    Map change point type to collection.

    :param str change_point_type: The change point type to display. It can be one of
    @see VALID_CHANGE_POINT_TYPES.
    :param CommandConfig command_config: Common configuration.
    :raises: ValueError if change_point_type is not valid.
    """
    if change_point_type not in VALID_CHANGE_POINT_TYPES:
        raise ValueError("{} is not a valid change point type.".format(change_point_type))

    if change_point_type == CHANGE_POINT_TYPE_UNPROCESSED:
        collection = command_config.unprocessed_change_points
    elif change_point_type == CHANGE_POINT_TYPE_PROCESSED:
        collection = command_config.processed_change_points
    else:
        collection = command_config.change_points
    return collection


def list_change_points(change_point_type, query, limit, no_older_than, human_readable,
                       hide_canaries, hide_wtdevelop, exclude_patterns, processed_types,
                       command_config):
    # pylint: disable=too-many-arguments, too-many-locals
    """
    List all points matching query and not excluded.

    :param str change_point_type: The change point type to display. It can be one of
    @see VALID_CHANGE_POINT_TYPES.
    :param dict query: Find change points matching this query.
    :param limit: The max number of items to display. None implies all.
    :type limit: int, None.
    :param bool human_readable: Print the output in human read able format.
    :param list(re) exclude_patterns: Filter any points matching this list of excludes.
    :param bool hide_canaries: Filter canaries in query. This happens before the
    excludes.
    :param bool hide_wtdevelop: Filter wtdevelop in query. This happens before the
    excludes.
    :param no_older_than: Filter points with start older than this number of days. None
    mean don't filter.
    :type  no_older_than: int or None.
    :param CommandConfig command_config: Common configuration.
    :param list(str) processed_types: Match processed_type when listing the processed
    change points.
    """
    LOG.debug('list %s', change_point_type)
    collection = map_collection(change_point_type, command_config)

    if change_point_type == CHANGE_POINT_TYPE_PROCESSED and processed_types:
        query['processed_type'] = {'$in': processed_types}
    pipeline = create_pipeline(query, limit, hide_canaries, hide_wtdevelop, no_older_than)
    cursor = collection.aggregate(pipeline)
    filtered_cursor = filter_excludes(cursor, query.keys(), exclude_patterns)

    if human_readable:
        for line in stream_human_readable(filtered_cursor, collection, limit, no_older_than):
            print(line, end='')
    else:
        for i, point in enumerate(filtered_cursor):
            LOG.info("list[%d] %s %s", i, collection.name,
                     stringify_json(point, compact=command_config.compact))
            print("//{}".format(i))
            print(stringify_json(point, compact=command_config.compact))
