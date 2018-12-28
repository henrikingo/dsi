"""
Functionality to mark change points.
"""
import structlog

from signal_processing.commands.helpers import stringify_json, filter_excludes

LOG = structlog.getLogger(__name__)

KEYS = ('suspect_revision', 'project', 'variant', 'task', 'test', 'thread_level')
"""
A tuple containing the keys for a unique identifier for a point.
"""


def get_identifier(point):
    """
    Get the identifer for a point.

    :param dict point: The full data for the point.
    :return: TYhe unique identifier for a point.
    :rtype: dict.
    """
    return {key: point[key] for key in KEYS}


def mark_change_points(processed_type, query, exclude_patterns, command_config):
    """
    Mark a point as hidden or real.

    :param str processed_type: Set the type.
    :see signal_processing.helpers.PROCESSED_TYPES.
    :param dict query: Find change points matching this query.
    :param list(re) exclude_patterns: Filter any points matching this list of excludes.
    :param CommandConfig command_config: Common configuration.
    """
    LOG.debug('mark points', processed_type=processed_type)
    collection = command_config.change_points

    for point in filter_excludes(collection.find(query), query.keys(), exclude_patterns):
        point['processed_type'] = processed_type
        del point['_id']
        LOG.info("matched %s\n", stringify_json(point, compact=command_config.compact))
        if not command_config.dry_run:
            result = command_config.processed_change_points.update(
                get_identifier(point), {"$set": point}, upsert=True)
            LOG.debug('mark points', result=result)
