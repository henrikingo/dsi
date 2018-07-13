"""
Functionality to mark change points.
"""
import logging
from signal_processing.commands.helpers import stringify_json, filter_excludes

LOG = logging.getLogger(__name__)


def update_change_points(processed_type, query, exclude_patterns, command_config):
    """
    update an existing processed change point.

    :param str processed_type: 'hidden' for hidden otherwise 'real'.
    :param dict query: Find change points matching this query.
    :param list(re) exclude_patterns: Filter any points matching this list of excludes.
    :param CommandConfig command_config: Common configuration.
    """
    LOG.debug('update "%s"', processed_type)
    collection = command_config.processed_change_points

    for point in filter_excludes(collection.find(query), query.keys(), exclude_patterns):
        LOG.info("update before: %s", stringify_json(point, compact=command_config.compact))
        point['processed_type'] = processed_type
        if not command_config.dry_run:
            update = {'$set': {
                'processed_type': processed_type}}
            res = collection.update_one({'_id': point['_id']}, update)
            LOG.debug('update: result "%r"', res.raw_result)
