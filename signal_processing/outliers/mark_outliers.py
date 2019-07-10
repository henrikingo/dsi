"""
Functionality to mark outliers.
"""
import structlog

from signal_processing.commands.helpers import stringify_json

LOG = structlog.getLogger(__name__)

KEYS = ('revision', 'project', 'variant', 'task', 'test', 'thread_level')
"""
A tuple containing the keys for a unique identifier for a point.
"""


def get_identifier(point):
    """
    Get the identifier for a point.
    :param dict point: The full data for the point.
    :return: TYhe unique identifier for a point.
    :rtype: dict.
    """
    return {key: point[key] for key in KEYS}


def mark_outlier(query, command_config, confirmed=True):
    """
    Mark an outlier.
    :param dict query: Find outlier matching this query.
    :param CommandConfig command_config: Common configuration.
    :param bool confirmed: whether the outlier was rejected vs confirmed.
    """
    LOG.debug('mark outlier', query=query)
    collection = command_config.outliers

    outlier = collection.find_one(query)
    if outlier:
        del outlier['_id']
        outlier['type'] = 'user-confirmed' if confirmed else 'user-rejected'
        LOG.info("matched\n", outlier=stringify_json(outlier, compact=command_config.compact))
        if not command_config.dry_run:
            result = command_config.marked_outliers.update(
                get_identifier(outlier),
                {'$currentDate': {
                    'last_updated_at': True
                },
                 '$set': outlier},
                upsert=True)
            LOG.debug('mark outlier', result=result)
    else:
        LOG.info('No outlier', query=query)
