"""
Unit tests for signal_processing/change_points.py.
"""
import unittest
from collections import OrderedDict

from mock import ANY, MagicMock, call, patch

from signal_processing.commands.manage import (
    create_linked_build_failures_view, create_points_indexes, create_unprocessed_change_points_view,
    manage, create_change_points_indexes)


class TestManage(unittest.TestCase):
    """
    Test Manage group command.
    """

    @patch('signal_processing.commands.manage.create_linked_build_failures_view')
    @patch('signal_processing.commands.manage.create_unprocessed_change_points_view')
    @patch('signal_processing.commands.manage.create_points_indexes')
    @patch('signal_processing.commands.manage.create_change_points_indexes')
    def test_manage(self, mock_change_points_indexes, mock_points_indexes,
                    mock_create_change_points_view, mock_create_build_failures_view):
        """ Test that manage calls the view and index functions. """
        mock_config = MagicMock(name='config', debug=0, log_file='/tmp/log_file')

        manage(mock_config)
        mock_points_indexes.assert_called_once()
        mock_change_points_indexes.assert_called_once()
        mock_create_change_points_view.assert_called_once()
        mock_create_build_failures_view.assert_called_once()


class TestCreatePointsIndex(unittest.TestCase):
    """
    Test manage.create_points_indexes function.
    """

    def test_create_points_indexes(self):
        """ Test create_points_indexes. """
        mock_points = MagicMock(name='point')
        mock_config = MagicMock(name='config', points=mock_points)

        create_points_indexes(mock_config)
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

        create_change_points_indexes(mock_config)
        calls = [
            call([('project', 1), ('variant', 1), ('task', 1), ('test', 1)]),
            call([('create_time', 1)])
        ]

        mock_change_points.create_index.assert_has_calls(calls)


class TestCreateBFView(unittest.TestCase):
    """
    Test manage.create_linked_build_failures_view function.
    """

    def test_create_bf_view(self):
        """ Test create_points_indexes. """
        mock_database = MagicMock(name='database')
        mock_config = MagicMock(name='config', database=mock_database)

        create_linked_build_failures_view(mock_config)
        view_name = 'linked_build_failures'
        source_collection_name = 'build_failures'
        mock_database.drop_collection.assert_called_once_with(view_name)
        mock_database.command.assert_called_once_with(
            OrderedDict([('create', view_name), ('pipeline', ANY), ('viewOn',
                                                                    source_collection_name)]))


class TestCreateChangePointView(unittest.TestCase):
    """
    Test manage.create_linked_build_failures_view function.
    """

    def test_create_change_point_view(self):
        """ Test create_points_indexes. """
        mock_database = MagicMock(name='database')
        mock_config = MagicMock(name='config', database=mock_database)

        create_unprocessed_change_points_view(mock_config)
        view_name = 'unprocessed_change_points'
        source_collection_name = 'change_points'
        mock_database.drop_collection.assert_called_once_with(view_name)
        mock_database.command.assert_called_once_with(
            OrderedDict([('create', view_name), ('pipeline', ANY), ('viewOn',
                                                                    source_collection_name)]))
