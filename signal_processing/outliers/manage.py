"""
Functionality to manage the outlier collections.
"""
import pymongo
import structlog

from signal_processing.util.mongo_util import create_indexes

LOG = structlog.getLogger(__name__)


def create_outliers_indexes(command_config):
    """
    Create indexes for the outliers collections.
     :param CommandConfig command_config: Common configuration.
    """
    # pylint: disable=invalid-name
    LOG.debug('create outliers indexes')
    create_indexes(command_config.outliers, [{
        'keys': [("project", pymongo.ASCENDING), ("variant", pymongo.ASCENDING),
                 ("task", pymongo.ASCENDING), ("test", pymongo.ASCENDING),
                 ("order", pymongo.ASCENDING)]
    }])


def manage(command_config):
    """
    Manage the database. At the moment, this command contains code to
    recreate the indexes, unprocessed change points view and linked build failures view.
     :param CommandConfig command_config: Common configuration.
    """

    create_outliers_indexes(command_config)
