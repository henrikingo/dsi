# -*- coding: utf-8 -*-
"""
Functionality to list change points.
"""
from __future__ import print_function

from datetime import datetime, timedelta
import logging
import math
import operator
import re
import sys
from collections import OrderedDict
import jinja2
from signal_processing.commands.helpers import filter_excludes, \
    stringify_json

LOG = logging.getLogger(__name__)

CHANGE_POINT_TYPE_PROCESSED = 'processed'
CHANGE_POINT_TYPE_UNPROCESSED = 'unprocessed'
CHANGE_POINT_TYPE_RAW = 'raw'
VALID_CHANGE_POINT_TYPES = [
    CHANGE_POINT_TYPE_PROCESSED, CHANGE_POINT_TYPE_UNPROCESSED, CHANGE_POINT_TYPE_RAW
]

DEFAULT_EVERGREEN_URL = 'https://evergreen.mongodb.com'
"""The default Evergreen URL."""


def calculate_ratio(statistics):
    """
    A helper to calculate next and previous mean ratio.

    :param dict test: The test data.
    :return: The mean ratios as a float. Nan is returned if either
    previous or next statistics are missing
    """
    if 'next' in statistics and 'previous' in statistics:
        before = statistics['previous']['mean']
        after = statistics['next']['mean']
        # latency, so reverse / abs.
        if after < 0 and before < 0:
            after = abs(statistics['previous']['mean'])
            before = abs(statistics['next']['mean'])
        delta = (after - before) / before
        return delta
    return float("nan")


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


def to_link(test, evergreen):
    """
    Jinja2 helper to get an evergreen link for a test.

    :param dict test: The test data.
    :return: A string url.
    """
    return "{evergreen}/version/{project}_{suspect_revision}".format(
        suspect_revision=test['suspect_revision'],
        project=test['project'].replace("-", "_"),
        evergreen=evergreen)


def to_query(test, collection):
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
  Tests: {{ point.change_points|length }}({{ point.min_magnitude }})
{% for test in point.change_points|group_sort %}
{%- set ratio = calculate_ratio(test.statistics) %}
  - {{ "%+3.0f%%"|format(ratio * 100) if not isnan(ratio) else ' Nan' }} `{{ point.suspect_revision }} {{ point.project }} {{ test.variant }} {{ test.task }} {{ test.test }} {{ test.thread_level }}`
{%- endfor %}
{% endfor %}
'''

ENVIRONMENT = jinja2.Environment()
ENVIRONMENT.globals.update({
    'calculate_ratio': calculate_ratio,
    'evergreen': DEFAULT_EVERGREEN_URL,
    'command_line': " ".join([value if value else "''" for value in sys.argv]),
    'now': datetime.utcnow,
    'format_no_older_than': format_no_older_than,
    'format_limit': format_limit,
    'isnan': math.isnan
})
ENVIRONMENT.filters.update({'link': to_link, 'query': to_query, 'group_sort': group_sort})
HUMAN_READABLE_TEMPLATE = ENVIRONMENT.from_string(HUMAN_READABLE_TEMPLATE_STR)


def create_pipeline(query,
                    limit,
                    hide_canaries,
                    hide_wtdevelop,
                    no_older_than,
                    sort_by_fortnight=True):
    # pylint: disable=too-many-arguments
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
        1. Add new fields.
            1. Add a fortnight field calculated from:
                 trunc( (start year * 100 + start week of year) / 2)
            1. Add a magnitude field which is the *log(mean ratios)*. The Log function ensures
            that drops are negative and improvements are positive. **This is important as the
            magnitude is sorted in ascending order.**
                * If next_mean is greater than 0 then the ratio is next / previous.
                * If next_mean is less than 0 then the ratio is previous / next as this
                is a latency. This ensures the sign is correct and that the sorting is
                sensible.
        1. Group the change points by project and revision.
            * Get newest create time.
            * Get newest start.
            * Get max magnitude.
            * Get min magnitude.
            * Get newest fortnight.
            * All change points.
        1. Project the fields listed above.
        1. Sort.
            * Sort by fortnight (descending) and min_magnitude (ascending). This is
            the default sort.
            OR
            * Sort by min_magnitude (ascending) and create time (descending).
        1. Limit the results if limit param is not None.

    :param dict query: The query to match against.
    :param limit: The max number of points to match. None means all.
    :type limit: int or None.
    :param bool show_canaries: Should canaries tests be excluded from the output.
    :param bool hide_wtdevelop: Should wtdevelop variants be excluded from the output.
    :param bool hide_wtdevelop: Should wtdevelop variants be excluded from the output.
    :param bool sort_by_fortnight: Sort the change points are sorted
    by the newest fortnight in the grouped change points and min_magnitude (descending).
    When set to False, the data is sorted by  min_magnitude and create time (descending).
    :param no_older_than: Exclude points with start fields older that this datetime.
                          None mean include all points.
    :type no_older_than: datetime or None
    :return: A list containing the aggregation pipeline.
    """
    pipeline = []
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

    if no_older_than is not None:
        pipeline.append({
            '$match': {
                'start': {
                    "$gt": datetime.utcnow() - timedelta(days=no_older_than)
                }
            }
        })

    pipeline.extend([
        {
            '$addFields': {
                'previous_mean': {
                    '$ifNull': ["$statistics.previous.mean", 1]
                },
                'next_mean': "$statistics.next.mean"
            }
        },
        {
            '$addFields': {
                'fortnight': {
                    '$trunc': {
                        '$divide': [{
                            '$sum': [{
                                '$multiply': [{
                                    '$year': {
                                        'date': "$start"
                                    }
                                }, 100]
                            }, {
                                '$week': {
                                    'date': "$start"
                                }
                            }]
                        }, 2]
                    }
                },
                'magnitude': {
                    '$ln': {
                        '$cond': [{
                            '$gt': ["$next_mean", 0]
                        }, {
                            '$divide': ['$next_mean', '$previous_mean']
                        }, {
                            '$divide': ['$previous_mean', '$next_mean']
                        }]
                    }
                }
            }
        },
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
                'fortnight': {
                    '$max': '$fortnight'
                },
                'change_points': {
                    '$push': '$$ROOT'
                }
            }
        },
        {
            '$project': {
                'project': '$_id.project',
                'suspect_revision': '$_id.suspect_revision',
                'change_points': 1,
                'start': 1,
                'fortnight': 1,
                'create_time': 1,
                'magnitude': 1,
                'min_magnitude': 1,
                'magnitudes': 1
            }
        },
    ])
    if sort_by_fortnight:
        sort_order = {'$sort': OrderedDict([('fortnight', -1), ('min_magnitude', 1)])}
    else:
        sort_order = {'$sort': OrderedDict([('min_magnitude', 1), ('create_time', -1)])}

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
                       hide_canaries, hide_wtdevelop, exclude_patterns, command_config):
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
    """
    LOG.debug('list %s', change_point_type)
    collection = map_collection(change_point_type, command_config)

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
