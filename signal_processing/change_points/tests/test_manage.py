"""
Unit tests for signal_processing/change_points/manage.py.
"""
import unittest
from collections import OrderedDict

from mock import ANY, MagicMock, call, patch

from signal_processing.change_points import manage

NS = 'signal_processing.change_points.manage'


def ns(relative_name):  # pylint: disable=invalid-name
    """Return a full name from a name relative to the tested module's name space."""
    return NS + '.' + relative_name


class TestManage(unittest.TestCase):
    """
    Test Manage group command.
    """

    @patch(ns('create_change_points_with_attachments_view'))
    @patch(ns('create_change_points_validators'))
    @patch(ns('create_linked_build_failures_view'))
    @patch(ns('create_unprocessed_change_points_view'))
    @patch(ns('create_points_indexes'))
    @patch(ns('create_change_points_indexes'))
    @patch(ns('create_processed_change_points_indexes'))
    def test_manage(self, mock_processed_indexes, mock_change_points_indexes, mock_points_indexes,
                    mock_create_change_points_view, mock_create_build_failures_view,
                    mock_change_points_validators, mock_change_points_with_attachments_view):
        # pylint: disable=invalid-name
        """ Test that manage calls the view and index functions. """
        mock_config = MagicMock(name='config', debug=0, log_file='/tmp/log_file')

        manage.manage(mock_config)
        mock_points_indexes.assert_called_once()
        mock_change_points_indexes.assert_called_once()
        mock_create_change_points_view.assert_called_once()
        mock_create_build_failures_view.assert_called_once()
        mock_processed_indexes.assert_called_once()
        mock_change_points_with_attachments_view.assert_called_once()
        mock_change_points_validators.assert_called_once()


class TestCreatePointsIndex(unittest.TestCase):
    """
    Test manage.create_points_indexes function.
    """

    def test_create_points_indexes(self):
        """ Test create_points_indexes. """
        mock_points = MagicMock(name='point')
        mock_config = MagicMock(name='config', points=mock_points)

        manage.create_points_indexes(mock_config)
        calls = [
            call([('project', 1), ('variant', 1), ('task', 1), ('test', 1), ('order', 1)]),
            call([('project', 1), ('variant', 1), ('task', 1), ('order', 1)])
        ]

        mock_points.create_index.assert_has_calls(calls)


class TestCreateChangePointsIndex(unittest.TestCase):
    """
    Test manage.create_change_points_indexes function.
    """

    def test_change_points_indexes(self):
        """ Test create_change_points_indexes. """
        mock_change_points = MagicMock(name='change_points')
        mock_config = MagicMock(name='config', change_points=mock_change_points)

        manage.create_change_points_indexes(mock_config)
        calls = [
            call([('project', 1), ('variant', 1), ('task', 1), ('test', 1)]),
            call([('create_time', 1)])
        ]

        mock_change_points.create_index.assert_has_calls(calls)


class TestCreateProcessedChangePointsIndex(unittest.TestCase):
    """
    Test manage.create_change_points_indexes function.
    """

    def test_create_indexes(self):
        """ Test create_processed_change_points_indexes. """
        mock_processed_change_points = MagicMock(name='processed_change_points')
        mock_config = MagicMock(name='config', processed_change_points=mock_processed_change_points)

        manage.create_processed_change_points_indexes(mock_config)
        calls = [
            call(
                [('suspect_revision', 1), ('project', 1), ('variant', 1), ('task', 1), ('test', 1),
                 ('thread_level', 1)],
                unique=True)
        ]

        mock_processed_change_points.create_index.assert_has_calls(calls)


class TestCreateBFView(unittest.TestCase):
    """
    Test manage.create_linked_build_failures_view function.
    """

    def test_create_bf_view(self):
        """ Test create_points_indexes. """
        mock_database = MagicMock(name='database')
        mock_config = MagicMock(name='config', database=mock_database)

        manage.create_linked_build_failures_view(mock_config)
        view_name = 'linked_build_failures'
        source_collection_name = 'build_failures'
        mock_database.drop_collection.assert_called_once_with(view_name)
        mock_database.command.assert_called_once_with(
            OrderedDict([('create', view_name), ('pipeline', ANY), ('viewOn',
                                                                    source_collection_name)]))


class TestChangePointsWithAttachmentsView(unittest.TestCase):
    """
    Test manage.create_change_points_with_attachments_view function.
    """

    def test_linked_change_point_view(self):
        """ Test create_change_points_with_attachments_view. """
        mock_database = MagicMock(name='database')
        mock_config = MagicMock(name='config', database=mock_database)

        manage.create_change_points_with_attachments_view(mock_config)
        view_name = 'change_points_with_attachments'
        source_collection_name = 'change_points'
        mock_database.drop_collection.assert_called_once_with(view_name)
        mock_database.command.assert_called_once_with(
            OrderedDict([('create', view_name), ('pipeline', ANY), ('viewOn',
                                                                    source_collection_name)]))


class TestUnprocessedChangePointView(unittest.TestCase):
    """
    Test manage.create_linked_build_failures_view function.
    """

    def test_unprocessed_change_point_view(self):
        """ Test create_unprocessed_change_points_view. """
        mock_database = MagicMock(name='database')
        mock_config = MagicMock(name='config', database=mock_database)

        manage.create_unprocessed_change_points_view(mock_config)
        view_name = 'unprocessed_change_points'
        source_collection_name = 'change_points_with_attachments'
        mock_database.drop_collection.assert_called_once_with(view_name)
        mock_database.command.assert_called_once_with(
            OrderedDict([('create', view_name), ('pipeline', ANY), ('viewOn',
                                                                    source_collection_name)]))


class TestCreateChangePointsValidators(unittest.TestCase):
    """
    Test validator functions.
    """

    def test_common_change_points_validator(self):
        """ Test common change_points validator. """
        mock_database = MagicMock(name='database')
        mock_change_points = MagicMock(name='change_points', database=mock_database)
        mock_change_points.name = "database.change_points"
        mock_config = MagicMock(name='command_config', change_points=mock_change_points)

        manage._create_common_change_points_validator(mock_config, mock_change_points)
        mock_database.command.assert_called_once_with(
            'collMod',
            'database.change_points',
            validator=ANY,
            validationAction='error') # yapf: disable
        args = mock_database.command.call_args_list

        # Get the validator from the call args list.
        validator = args[0][1]['validator']

        # Only match on the all_suspect_revisions property.
        self.assertTrue('$jsonSchema' in validator)
        self.assertTrue('required' in validator['$jsonSchema'])
        self.assertTrue('all_suspect_revisions' in validator['$jsonSchema']['required'])
        self.assertDictContainsSubset({
            'all_suspect_revisions': {
                'bsonType': 'array',
                'items': {
                    'type': 'string'
                },
                'minItems': 1,
                'description': "must be an array of strings with at least one element"
            }
        }, validator['$jsonSchema']['properties'])

    @patch(ns('_create_common_change_points_validator'))
    def test_change_points_validator(self, mock_common_validator):
        """ Test change_points validator. """
        mock_database = MagicMock(name='database')
        mock_change_points = MagicMock(name='change_points', database=mock_database)
        mock_processed_change_points = MagicMock(
            name='processed_change_points', database=mock_database)
        mock_config = MagicMock(
            name='command_config',
            change_points=mock_change_points,
            processed_change_points=mock_processed_change_points)

        manage.create_change_points_validators(mock_config)
        mock_common_validator.assert_has_calls([
            call(mock_config, mock_change_points),
            call(mock_config, mock_processed_change_points)
        ])
