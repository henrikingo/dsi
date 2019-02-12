"""
Functionality to mute outliers.
"""
import pymongo
import structlog

from signal_processing.commands.helpers import get_query_for_points

LOG = structlog.getLogger(__name__)

KEYS = ('revision', 'project', 'variant', 'task', 'test', 'thread_level')
"""
A tuple containing the keys for a unique identifier for a point.
"""


def get_identifier(mute):
    """
    Get the identifier for a mute.

    :param dict mute: The full data for the point.
    :return: TYhe unique identifier for a point.
    :rtype: dict.
    """
    return {key: mute[key] for key in KEYS}


def get_mute(test_identifier, mute_outliers_collection):
    """
    Get the mute for the test / task.

    :param dict() test_identifier: The identifier for the test /task.
    :param pymongo.collection mute_outliers_collection: The identifier for the test /task.

    :return: The mute matching the identifier
    :rtype: dict or None
    """
    # get the first point or None
    mutes = mute_outliers_collection.find(test_identifier).sort([('order',
                                                                  pymongo.DESCENDING)]).limit(1)
    mute = next(mutes, None)
    LOG.debug('get_mute', test_identifier=test_identifier, mute=mute)
    return mute


def mute_outliers(test_identifier, enabled, command_config):
    """
    Mute OR Unmute outliers for a task. A task is unmuted by setting the enabled flag to False.

    :param dict test_identifier: The identifier for this test / task.
    :param bool enabled: Enable or disable the mute.
    :param CommandConfig command_config: Common configuration.
    """
    LOG.debug('mark outlier', test_identifier=test_identifier)
    collection = command_config.points

    mute = get_mute(test_identifier, command_config.mute_outliers)
    if mute is None:
        query = get_query_for_points(test_identifier)
        mute = next(collection.find(query).sort([('order', pymongo.DESCENDING)]).limit(1), None)
        if mute:
            mute.update(**test_identifier)
            del mute['results']
        identifier = test_identifier
    else:
        identifier = {'_id': mute['_id']}
        del mute['last_updated_at']

    if mute:
        # ensure that this point can be found with the test identifier
        mute['enabled'] = enabled
        LOG.info("matched", mute=mute)
        if not command_config.dry_run:
            result = command_config.mute_outliers.update_one(
                identifier, {'$currentDate': {
                    'last_updated_at': True
                },
                             '$set': mute}, upsert=True)
            LOG.debug('mute outliers for task', result=result)
    else:
        LOG.info('No matching task', query=query)
