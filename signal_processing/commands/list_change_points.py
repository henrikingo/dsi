"""
Functionality to list change points.
"""
from __future__ import print_function
import logging
import re

from signal_processing.commands.helpers import stringify_json, filter_excludes

LOG = logging.getLogger(__name__)

CHANGE_POINT_TYPE_PROCESSED = 'processed'
CHANGE_POINT_TYPE_UNPROCESSED = 'unprocessed'
CHANGE_POINT_TYPE_RAW = 'raw'
VALID_CHANGE_POINT_TYPES = [
    CHANGE_POINT_TYPE_PROCESSED, CHANGE_POINT_TYPE_UNPROCESSED, CHANGE_POINT_TYPE_RAW
]

DEFAULT_EVERGREEN_URL = 'https://evergreen.mongodb.com'
"""The default Evergreen URL."""


def render_human_readable(index, point, collection_name):
    """
    Render a point into a human readable string.

    :param int index: The index of the point.
    :param dict point: The change point data.
    :param str collection_name: The name of the collection.
    :return: The human readable point.
    """
    link = "{evergreen}/version/{project}_{revision}".format(
        evergreen=DEFAULT_EVERGREEN_URL,
        project=point['project'],
        revision=point['suspect_revision'])

    template = "db.{0}.find({{project: '{project}', "\
                "suspect_revision: '{suspect_revision}' }})"
    query_string = template.format(collection_name, **point)
    # pylint: disable=C0303
    output = [
        """
- ID:       `{0}`  
  Link:     <{1}>  
  Project:  `{project}`  
  Revision: `{suspect_revision}`  
  Query:    `{2}`  
  Tests: {3}  """.format(index, link, query_string, len(point['change_points']), **point)
    ]
    for change_point in point['change_points']:
        if 'statistics' in change_point and \
            'next' in change_point['statistics'] and \
            'previous' in change_point['statistics']:
            percentage_change = "{0:.0f}%".format(
                100 * change_point['statistics']['previous']['mean'] / change_point['statistics']
                ['next']['mean'] - 100)
        else:
            percentage_change = "NaN"
        output.append("  - {0:>3} `{variant}` `{task}` `{test}` `{thread_level}`".format(
            percentage_change, **change_point))

    return "\n".join(output)


def create_pipeline(query, limit, show_canaries, show_wtdevelop):
    # pylint: disable=too-many-arguments
    """
    Create an aggregation pipeline for list change points.

    :param dict query: The query to match against.
    :param limit: The max number of points to match. None means all.
    :type limit: int or None.
    :param bool show_canaries: Should canaries tests be excluded from the output.
    :param bool show_wtdevelop: Should wtdevelop variants be excluded from the output.
    :return: A list containing the aggregation pipeline.
    """

    pipeline = [{
        '$match': query
    }, {
        '$group': {
            '_id': {
                'project': '$project',
                'suspect_revision': '$suspect_revision'
            },
            'change_points': {
                '$push': '$$ROOT'
            }
        }
    }, {
        '$project': {
            'project': '$_id.project',
            'suspect_revision': '$_id.suspect_revision',
            'change_points': 1
        }
    }]

    if not show_canaries:
        pipeline.insert(0, {
            '$match': {
                'test': {
                    '$not': re.compile('^(canary_|fio_|NetworkBandwidth)')
                }
            }
        })

    if not show_wtdevelop:
        pipeline.insert(0, {'$match': {'variant': {'$not': re.compile('^wtdevelop')}}})

    if limit is not None:
        pipeline.append({'$limit': limit})
    return pipeline


def list_change_points(change_point_type, query, limit, human_readable, show_canaries,
                       show_wtdevelop, exclude_patterns, command_config):
    # pylint: disable=too-many-arguments
    """
    List all points matching query and not excluded.

    :param str change_point_type: The change point type to display. It can be one of
    @see VALID_CHANGE_POINT_TYPES.
    :param dict query: Find change points matching this query.
    :param limit: The max number of items to display. None implies all.
    :type limit: int, None.
    :param bool human_readable: Print the output in human read able format.
    :param list(re) exclude_patterns: Filter any points matching this list of excludes.
    :param bool show_canaries: Filter canaries in query. This happens before the
    excludes.
    :param bool show_wtdevelop: Filter wtdevelop in query. This happens before the
    excludes.
    :param CommandConfig command_config: Common configuration.
    """
    LOG.debug('list %s', change_point_type)

    if change_point_type not in VALID_CHANGE_POINT_TYPES:
        raise ValueError("{} is not a valid change point type".format(change_point_type))

    if change_point_type == CHANGE_POINT_TYPE_UNPROCESSED:
        collection = command_config.unprocessed_change_points
    elif change_point_type == CHANGE_POINT_TYPE_PROCESSED:
        collection = command_config.processed_change_points
    else:
        collection = command_config.change_points

    pipeline = create_pipeline(query, limit, show_canaries, show_wtdevelop)

    cursor = collection.aggregate(pipeline)
    for i, point in enumerate(filter_excludes(cursor, query.keys(), exclude_patterns)):
        LOG.info("list[%d] %s %s", i, collection.name,
                 stringify_json(point, compact=command_config.compact))
        if not human_readable:
            print("//{}".format(i))
            print(stringify_json(point, compact=command_config.compact))
        else:
            print(render_human_readable(i, point, collection.name))
