"""
Functionality to unmark change points.
"""
import structlog

from signal_processing.commands.helpers import filter_excludes

LOG = structlog.getLogger(__name__)


def unmark_change_points(processed_type, query, exclude_patterns, command_config):
    """
    Delete marked change points.

    :param str processed_type: 'hidden' for hidden otherwise 'real'.
    :param dict query: Find change points matching this query.
    :param list(re) exclude_patterns: Filter any points matching this list of excludes.
    :param CommandConfig command_config: Common configuration.
    """
    LOG.debug('unmark', processed_type=processed_type)
    collection = command_config.processed_change_points

    keys = query.keys()
    if processed_type:
        query['processed_type'] = processed_type

    count = 0
    for point in filter_excludes(collection.find(query), keys, exclude_patterns):
        LOG.info("unmark", point=point)
        count += 1
        if not command_config.dry_run:
            result = collection.remove({'_id': point['_id']})
            LOG.debug('unmark', _id=point['_id'], result=result)
    LOG.info('unmark', count=count, dry_run=command_config.dry_run)
