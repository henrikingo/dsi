"""
Functionality to unmark outlier.
"""
import structlog

from signal_processing.commands.helpers import stringify_json

LOG = structlog.getLogger(__name__)

KEYS = ('revision', 'project', 'variant', 'task', 'test', 'thread_level')
"""
A tuple containing the keys for a unique identifier for a point.
"""


def get_identifier(outlier):
    """
    Get the identifier for an outlier.
    :param dict outlier: The full data for the outlier.
    :return: TYhe unique identifier for a outlier.
    :rtype: dict.
    """
    return {key: outlier[key] for key in KEYS}


def unmark_outlier(query, command_config):
    """
    Unmark an outlier.
    :param dict query: Find outlier matching this query.
    :param CommandConfig command_config: Common configuration.
    """
    LOG.debug('unmark outlier', query=query)
    collection = command_config.marked_outliers

    outlier = collection.find_one(query, {'_id': 1})
    if outlier:
        LOG.info("matched\n", outlier=stringify_json(outlier, compact=command_config.compact))
        if not command_config.dry_run:
            result = collection.delete_one({'_id': outlier['_id']})
            LOG.debug('unmark outlier', result=result)
    else:
        LOG.info('No outliers', query=query)
