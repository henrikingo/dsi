"""
Functionality to mark change points.
"""
import logging

from signal_processing.commands.helpers import stringify_json, filter_excludes

LOG = logging.getLogger(__name__)


def list_change_points(processed, query, exclude_patterns, command_config):
    """
    List all points matching query and not excluded.

    :param bool processed: list processed_change_points if True other wise change_points.
    :param dict query: Find change points matching this query.
    :param list(re) exclude_patterns: Filter any points matching this list of excludes.
    :param CommandConfig command_config: Common configuration.
    """
    LOG.debug('list %s', 'processed' if processed else 'unprocessed')
    if processed:
        collection = command_config.processed_change_points
    else:
        collection = command_config.change_points

    for i, point in enumerate(filter_excludes(collection.find(query), query.keys(),
                                              exclude_patterns)):
        LOG.info("list[%d] %s %s", i, collection.name,
                 stringify_json(point, compact=command_config.compact))
