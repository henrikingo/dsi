"""
Functionality to create or recreate the unprocessed change points view.
"""
from collections import OrderedDict
import structlog

LOG = structlog.getLogger(__name__)


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


def create_unprocessed_change_points_view(command_config):
    """
    Create the unprocessed change points view.

    :param CommandConfig command_config: Common configuration.
    """
    # pylint: disable=invalid-name
    LOG.debug('starting')
    database = command_config.database

    # The pipeline for the unprocessed change points view. If you change this pipeline
    # then you must also update ../README.md#unprocessed-change-points-view.
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
        # Lookup hidden processed change points as processed_change_points field.
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

                # Note: we are only matching 'processed_type', 'hidden', this cuts down
                # on the size of the embedded hidden_processed_change_points.
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
                                {'$eq': ['$processed_type', 'hidden']}
                            ]
                        }
                    }
                }],
                'as': 'hidden_processed_change_points'
            }
        },

        # The following match filters documents from the lookup phase with
        # any processed_change_points. We only lookup hidden points so any document
        # with a non-empty processed_change_points array should be hidden.
        {'$match': {'$expr': {'$eq': [0, {'$size': '$hidden_processed_change_points'}]}}},

        # Filter out real change points that have matching BF ticket.
        # Note the broad match: We expect a single BF per commit.
        # IOW a commit can only introduce one regression and all change_points
        # are therefore immediately covered by the same BF ticket.

        # Build Failures contains 2 array fields which can have 0 or more elements:
        #  1. first_failing_revision: A list of githashes representing the first failures.
        #  2. fix_revision: A list of githashes representing the fixs.
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
        # Filter any change points with no attached build failures.
        {'$match': {'$expr': {'$eq': [0, {'$size': '$build_failures'}]}}},
        # Project a clean document without the empty build_failures.
        {'$project': {'hidden_processed_change_points': False, 'build_failures': False}}
    ] # yapf:disable

    view_name = 'unprocessed_change_points'
    source_collection_name = 'change_points'
    database.drop_collection(view_name)
    database.command(OrderedDict([('create', view_name),
                                  ('pipeline', pipeline),
                                  ('viewOn', source_collection_name)])) # yapf: disable


def manage(command_config):
    """
    Manage the database. At the moment, this comand only contains code to
    recreate the unprocessed change points view.

    :param CommandConfig command_config: Common configuration.
    """

    create_unprocessed_change_points_view(command_config)
    create_linked_build_failures_view(command_config)
