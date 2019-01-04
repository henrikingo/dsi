"""
Functionality to create or recreate the unprocessed change points view.
"""
from collections import OrderedDict

import pymongo
import structlog

LOG = structlog.getLogger(__name__)


def _create_indexes(collection, indexes):
    """
    Create indexes for a given collections.

    :param pymongo.Collection collection: The target collection.
    :param list(dict) indexes: The indexes to create.
    """
    LOG.debug('create indexes', collection=collection, indexes=indexes)
    for index in indexes:
        options = index['options'] if 'options' in index else {}
        collection.create_index(index['keys'], **options)


def _create_validator(collection, validator, action='error'):
    """
    Modify a collection to apply validation rules to a collection.

    :param pymongo.Collection collection: The target collection.
    :param dict validator: The validation rules.
    :param str action: The validation action. This controls the response to a
    validation issue. The default is error.

    See `schema-validation <https://docs.mongodb.com/manual/core/schema-validation/>`_
    See `json-schema <http://json-schema.org/>`_
    """
    LOG.debug('_create_validator', collection=collection, validator=validator)
    collection.database.command(
        'collMod',
        collection.name,
        validator=validator,
        validationAction=action) # yapf: disable


def create_points_indexes(command_config):
    """
    Create indexes for the points collections.

    :param CommandConfig command_config: Common configuration.
    """
    # pylint: disable=invalid-name
    LOG.debug('create points indexes')
    _create_indexes(command_config.points, [{
        'keys': [("project", pymongo.ASCENDING), ("variant", pymongo.ASCENDING),
                 ("task", pymongo.ASCENDING), ("test", pymongo.ASCENDING),
                 ("order", pymongo.ASCENDING)]
    }, {
        'keys': [("project", pymongo.ASCENDING), ("variant", pymongo.ASCENDING),
                 ("task", pymongo.ASCENDING), ("order", pymongo.ASCENDING)]
    }])


def create_change_points_indexes(command_config):
    """
    Create indexes for the change_points collections.

    :param CommandConfig command_config: Common configuration.
    """
    # pylint: disable=invalid-name
    LOG.debug('create change points indexes')
    _create_indexes(command_config.change_points, [{
        'keys': [("project", pymongo.ASCENDING), ("variant", pymongo.ASCENDING),
                 ("task", pymongo.ASCENDING), ("test", pymongo.ASCENDING)]
    }, {
        'keys': [("create_time", pymongo.ASCENDING)]
    }])


# TODO: TIG-1173 Add more validation to signal processing collections
def _create_common_change_points_validator(command_config, collection):
    """
    Create change_points and processed change_points common validation rules.

    :param CommandConfig command_config: Common configuration.
    :param pymongo.Collection collection: The target collection.
    """
    # pylint: disable=invalid-name, unused-argument
    LOG.debug('create common change points validation rules', collection=collection.name)
    _create_validator(
        collection, {
            '$jsonSchema': {
                'bsonType': 'object',
                'required': ['all_suspect_revisions'],
                'properties': {
                    'all_suspect_revisions': {
                        'bsonType': 'array',
                        'items': {
                            'type': 'string'
                        },
                        'minItems': 1,
                        'description': "must be an array of strings with at least one element"
                    }
                }
            }
        })


def create_change_points_validators(command_config):
    """
    Create change_points validation rules.

    :param CommandConfig command_config: Common configuration.
    """
    # pylint: disable=invalid-name
    LOG.debug('create change_points validation rules')
    _create_common_change_points_validator(command_config, command_config.change_points)
    _create_common_change_points_validator(command_config, command_config.processed_change_points)


def create_processed_change_points_indexes(command_config):
    """
    Create indexes for the processed change_points collections.

    :param CommandConfig command_config: Common configuration.
    """
    # pylint: disable=invalid-name
    LOG.debug('create processed change points indexes')
    _create_indexes(command_config.processed_change_points, [{
        'keys': [("suspect_revision", pymongo.ASCENDING), ("project", pymongo.ASCENDING),
                 ("variant", pymongo.ASCENDING), ("task", pymongo.ASCENDING),
                 ("test", pymongo.ASCENDING), ("thread_level", pymongo.ASCENDING)],
        'options': {
            'unique': True
        }
    }])


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
    ] # yapf:disable

    view_name = 'change_points_with_attachments'
    source_collection_name = 'change_points'
    database.drop_collection(view_name)
    database.command(OrderedDict([('create', view_name),
                                  ('pipeline', pipeline),
                                  ('viewOn', source_collection_name)])) # yapf: disable


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
        {'$match': {'processed_change_points.processed_type': {'$ne': 'hidden'}}},

        # Filter out real change points that have matching BF ticket.
        {'$match': {'$expr': {'$eq': [0, {'$size': '$build_failures'}]}}},

        # Project a clean document without the empty build_failures.
        {'$project': {'processed_change_points': False, 'build_failures': False}}
    ] # yapf:disable

    view_name = 'unprocessed_change_points'
    source_collection_name = 'change_points_with_attachments'
    database.drop_collection(view_name)
    database.command(OrderedDict([('create', view_name),
                                  ('pipeline', pipeline),
                                  ('viewOn', source_collection_name)])) # yapf: disable


def manage(command_config):
    """
    Manage the database. At the moment, this comand contains code to
    recreate the indexes, unprocessed change points view and linked build failures view.

    :param CommandConfig command_config: Common configuration.
    """

    create_processed_change_points_indexes(command_config)
    create_points_indexes(command_config)
    create_change_points_indexes(command_config)

    create_change_points_with_attachments_view(command_config)
    create_unprocessed_change_points_view(command_config)
    create_linked_build_failures_view(command_config)

    create_change_points_validators(command_config)
