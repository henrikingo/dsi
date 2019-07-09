"""
Functionality to create or recreate the unprocessed change points view.
"""
import json
import os
from collections import OrderedDict

import click
import pymongo
import structlog

import signal_processing.commands.helpers as helpers
import signal_processing.util.mongo_util as mongo_util

LOG = structlog.getLogger(__name__)


def _create_collection_map(command_config):
    """
    Create a map to access various collections.

    :param CommandConfig command_config: Command configuration.
    :return: Dictionary of collections names to collection objects.
    """
    return {
        helpers.POINTS: command_config.points,
        helpers.CHANGE_POINTS: command_config.change_points,
        helpers.PROCESSED_CHANGE_POINTS: command_config.processed_change_points,
    }


INDEXES_TO_CREATE = {
    helpers.POINTS: [
        {
            'keys': [("project", pymongo.ASCENDING), ("variant", pymongo.ASCENDING),
                     ("task", pymongo.ASCENDING), ("test", pymongo.ASCENDING), ("order",
                                                                                pymongo.ASCENDING)]
        },
        {
            'keys': [("project", pymongo.ASCENDING), ("variant", pymongo.ASCENDING),
                     ("task", pymongo.ASCENDING), ("order", pymongo.ASCENDING)]
        },
    ],
    helpers.CHANGE_POINTS: [
        {
            'keys': [("project", pymongo.ASCENDING), ("variant", pymongo.ASCENDING),
                     ("task", pymongo.ASCENDING), ("test", pymongo.ASCENDING)]
        },
        {
            'keys': [("create_time", pymongo.ASCENDING)],
        },
    ],
    helpers.PROCESSED_CHANGE_POINTS: [{
        'keys': [("suspect_revision", pymongo.ASCENDING), ("project", pymongo.ASCENDING),
                 ("variant", pymongo.ASCENDING), ("task", pymongo.ASCENDING),
                 ("test", pymongo.ASCENDING), ("thread_level", pymongo.ASCENDING)],
        'options': {
            'unique': True
        }
    }],
}

COLLECTIONS_TO_INDEX = INDEXES_TO_CREATE.keys()
DIRECTORY = os.path.dirname(__file__)


def _get_database_validator(operator, directory=DIRECTORY):
    """
    Get a database validator/filter to be applied to a collection from a json file
    :param operator: name of the validator
    :return: the validator object
    """
    with open(os.path.join(directory, 'database_validators',
                           '{}.json'.format(operator))) as operator_file:
        return json.load(operator_file)


def _create_common_change_points_validator(collection):
    """
    Create change_points and processed change_points common validation rules.

    :param pymongo.Collection collection: The target collection.
    """
    # pylint: disable=invalid-name, unused-argument
    LOG.debug('create common change points validation rules', collection=collection.name)
    mongo_util.create_validator(collection, _get_database_validator('change_points_validator'))


def create_build_failure_validator(collection):
    """
    Create build_failure validation rules.

    :param pymongo.Collection collection: The target collection.
    """
    # pylint: disable=invalid-name, unused-argument
    LOG.debug('create build failures validation rules', collection=collection.name)
    mongo_util.create_validator(
        collection, _get_database_validator('build_failures_validator'), action='warn')


def create_change_points_validators(command_config):
    """
    Create change_points validation rules.

    :param CommandConfig command_config: Common configuration.
    """
    # pylint: disable=invalid-name
    LOG.debug('create change_points validation rules')
    _create_common_change_points_validator(command_config.change_points)
    _create_common_change_points_validator(command_config.processed_change_points)


def create_linked_build_failures_view(command_config):
    """
    Create the linked build failures view.

    :param CommandConfig command_config: Common configuration.
    """
    # pylint: disable=invalid-name
    LOG.debug('starting')
    database = command_config.database

    pipeline = [{
        '$addFields': {
            'revision': {
                '$concatArrays': ['$first_failing_revision', '$fix_revision']
            }
        }
    }, {
        '$unwind': {
            'path': '$revision'
        }
    }, {
        '$lookup': {
            'from':
                'change_points',
            'let': {
                'revision': '$revision',
                'project': '$project'
            },
            'pipeline': [{
                '$match': {
                    '$expr': {
                        '$and': [{
                            '$in': ['$$revision', '$all_suspect_revisions'],
                        }, {
                            '$in': ['$project', '$$project']
                        }]
                    }
                }
            }],
            'as':
                'linked_change_points'
        }
    }, {
        '$match': {
            'linked_change_points': {
                '$not': {
                    '$size': 0
                }
            }
        }
    }]
    view_name = 'linked_build_failures'
    source_collection_name = 'build_failures'
    database.drop_collection(view_name)
    database.command(OrderedDict([('create', view_name),
                                  ('pipeline', pipeline),
                                  ('viewOn', source_collection_name)])) # yapf: disable


def create_change_points_with_attachments_view(command_config):
    """
    Create the change_points with attachments view.

    This view contains all change points.

    This view provides a convenience to lookup change points with
    the associated processed_change_points (either acknowledged or
    hidden) and associated build_failures embedded
    into sub-document arrays.

    The processed change_points lookup is through the common suspect_revision
    fields.

    TODO: they should be linked through all_suspect_revisions
    but this would be too slow at the moment.

    change_points are linked to the build_failures through the revsions and
    all_suspect_revision fields.

    :param CommandConfig command_config: Common configuration.
    """
    # pylint: disable=invalid-name
    LOG.debug('starting')
    database = command_config.database

    # This view provides a convenience to lookup change points with
    # the associated processed_change_points (either acknowledged or
    # hidden) and associated build_failures embedded
    # into sub-document arrays.
    pipeline = [
        # pylint: disable=line-too-long
        {
            '$match': {
                '$comment':
                'This view represents all the change points with attached '
                'processed change points and Build Failures.'
            }
        },
        # Lookup processed change points as processed_change_points field.
        {
            '$lookup': {
                'from':
                    'processed_change_points',
                'let': {
                    'project': '$project',
                    'variant': '$variant',
                    'task': '$task',
                    'test': '$test',
                    'thread_level': '$thread_level',
                    'suspect_revision': '$suspect_revision'
                },

                'pipeline': [{
                    '$match': {
                        '$expr': {
                            '$and': [
                                {'$eq': ['$project', '$$project']},
                                {'$eq': ['$variant', '$$variant']},
                                {'$eq': ['$task', '$$task']},
                                {'$eq': ['$test', '$$test']},
                                {'$eq': ['$thread_level', '$$thread_level']},
                                {'$eq': ['$suspect_revision', '$$suspect_revision']},
                            ]
                        }
                    },

                }],
                'as': 'processed_change_points'
            }
        },
        # Note the broad match: We expect a single BF per commit.
        # IOW a commit can only introduce one regression and all change_points
        # are therefore immediately covered by the same BF ticket.

        # Build Failures contains 2 array fields which can have 0 or more elements:
        #  1. first_failing_revision: A list of githashes representing the first failures.
        #  2. fix_revision: A list of githashes representing the fixes.
        # For any given project there should only be a single githash for first_failing_revision.
        # For fix_revision, it is possible to have multiple revisions / project. For example,
        # an issue is fixed in stages. It is also possible that the field can be empty or missing.

        # Lookup:
        # Match / filter the following:
        #   1. matching each BF matching the project.
        #   2. excluding BFs with no first_failing_revision and fix_revision (as early as possible).
        # Project first_failing_revision / fix_revision into revision.
        # Unwind revision.
        # Match revision against all_suspect_revisions.
        {
            '$lookup': {
                'from': 'build_failures',
                'let': {
                    'project': '$project',
                    'all_suspect_revisions': '$all_suspect_revisions'},
                'pipeline': [
                    {'$match': {'$expr': {'$and': [
                        {'$in': ['$$project', '$project']},
                        {'$or': [{'$ne': [0, {'$size': '$first_failing_revision'}]},
                                 {'$ne': [0, {'$size': '$fix_revision'}]}]}
                        ]}}},
                    {'$project': {'revision': {'$concatArrays': ['$first_failing_revision',
                                                                 '$fix_revision']}}},
                    {'$unwind': '$revision'},
                    {'$match': {'$expr': {'$and': [{'$in': ['$revision',
                                                            '$$all_suspect_revisions']}]}}}
                ],
                'as': 'build_failures'
            }
        },
    ]  # yapf:disable

    view_name = 'change_points_with_attachments'
    source_collection_name = 'change_points'
    database.drop_collection(view_name)
    database.command(OrderedDict([('create', view_name),
                                  ('pipeline', pipeline),
                                  ('viewOn', source_collection_name)]))  # yapf: disable


def create_unprocessed_change_points_view(command_config):
    """
    Create the unprocessed change points view.

    :param CommandConfig command_config: Common configuration.
    :method: `create_change_points_with_attachments_view` performs
    the heavy lifting in the lookups.
    """
    # pylint: disable=invalid-name
    LOG.debug('starting')
    database = command_config.database

    # The pipeline for the unprocessed change points view.
    pipeline = [
        # pylint: disable=line-too-long
        {
            '$match': {
                '$comment':
                'This view represents the change points which have not '
                'been hidden and are not associated with a Build Failure. '
                'See https://github.com/10gen/dsi/tree/master/signal_processing/README.md#unprocessed-change-points-collection '
                'for more details about this view.'
            }
        },

        # The following match filters documents from the lookup phase with
        # any processed_change_points.
        {'$match': {'$expr': {'$eq': [0, {'$size': '$processed_change_points'}]}}},

        # Filter out real change points that have matching BF ticket.
        {'$match': {'$expr': {'$eq': [0, {'$size': '$build_failures'}]}}},

        # Project a clean document without the empty build_failures.
        {'$project': {'processed_change_points': False, 'build_failures': False}}
    ]  # yapf:disable

    view_name = 'unprocessed_change_points'
    source_collection_name = 'change_points_with_attachments'
    database.drop_collection(view_name)
    database.command(OrderedDict([('create', view_name),
                                  ('pipeline', pipeline),
                                  ('viewOn', source_collection_name)]))  # yapf: disable


def create_indexes(collection_map, collections, drop=False, force=False):
    """
    Create indexes on the specified collections.

    :param dict collection_map: Map of collection names to collection objects.
    :param list(str) collections: collections to index.
    :param boolean drop: Indexes be dropped before creating.
    :param boolean force: Don't prompt user before dropping indexes.
    :return:
    """
    for collection in collections:
        if drop:
            msg = 'Are you sure you want to drop indexes on {0}'.format(collection)
            if force or click.confirm(msg):
                mongo_util.drop_indexes(collection_map[collection], INDEXES_TO_CREATE[collection])

        mongo_util.create_indexes(collection_map[collection], INDEXES_TO_CREATE[collection])


def manage(command_config, collections, drop=False, force=False):
    """
    Manage the database. At the moment, this command contains code to
    recreate the indexes, unprocessed change points view and linked build failures view.

    :param CommandConfig command_config: Common configuration.
    :param list(str) collections: collections to index.
    :param boolean drop: Indexes be dropped before creating.
    :param boolean force: Don't prompt user before dropping indexes.
    """

    create_indexes(_create_collection_map(command_config), collections, drop, force)

    create_change_points_with_attachments_view(command_config)
    create_unprocessed_change_points_view(command_config)
    create_linked_build_failures_view(command_config)

    create_change_points_validators(command_config)
    create_build_failure_validator(command_config.build_failures)
