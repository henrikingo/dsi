"""
Functionality to mark change points.
"""
import logging

from signal_processing.commands import stringify_json, filter_excludes

LOG = logging.getLogger(__name__)


def mark_change_points(processed_type, query, exclude_patterns, command_config):
    """
    Mark a point as hidden or real.

    :param str processed_type: 'hidden' for hidden otherwise 'real'.
    :param dict query: Find change points matching this query.
    :param list(re) exclude_patterns: Filter any points matching this list of excludes.
    :param CommandConfig command_config: Common configuration.
    """
    LOG.debug('mark points "%s"', processed_type)
    collection = command_config.change_points

    for point in filter_excludes(collection.find(query), query.keys(), exclude_patterns):
        point['processed_type'] = processed_type
        del point['_id']
        LOG.info("matched %s\n", stringify_json(point, compact=command_config.compact))
        if not command_config.dry_run:
            command_config.processed_change_points.insert(point)
