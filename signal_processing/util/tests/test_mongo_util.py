"""
Unit tests for signal_processing/util/mongo_util.py.
"""
import unittest

from mock import MagicMock, call

from signal_processing.util import mongo_util

NS = 'signal_processing.util.mongo_util'


def ns(relative_name):  # pylint: disable=invalid-name
    """Return a full name from a name relative to the tested module's name space."""
    return NS + '.' + relative_name


class TestCreateIndexes(unittest.TestCase):
    def test_no_indexes(self):
        mock_collection = MagicMock()
        mongo_util.create_indexes(mock_collection, [])
        mock_collection.create_index.assert_not_called()

    def test_one_index(self):
        mock_collection = MagicMock()
        mock_index = {'keys': 'this is the key'}
        mongo_util.create_indexes(mock_collection, [mock_index])
        mock_collection.create_index.assert_called_with(mock_index['keys'])

    def test_multiple_indexes(self):
        mock_collection = MagicMock()
        mock_indexes = [{'keys': 'this is the key 1'}, {'keys': {'a': 'more', 'complex': 'key'}}]
        calls = [
            call(mock_indexes[0]['keys']),
            call(mock_indexes[1]['keys']),
        ]
        mongo_util.create_indexes(mock_collection, mock_indexes)
        mock_collection.create_index.assert_has_calls(calls)


class TestDropIndexes(unittest.TestCase):
    def test_no_indexes(self):
        mock_collection = MagicMock()
        mongo_util.drop_indexes(mock_collection, [])
        mock_collection.drop_index.assert_not_called()

    def test_one_index(self):
        mock_collection = MagicMock()
        mock_index = {'keys': 'this is the key'}
        mongo_util.drop_indexes(mock_collection, [mock_index])
        mock_collection.drop_index.assert_called_with(mock_index['keys'])

    def test_multiple_indexes(self):
        mock_collection = MagicMock()
        mock_indexes = [{'keys': 'this is the key 1'}, {'keys': {'a': 'more', 'complex': 'key'}}]
        calls = [
            call(mock_indexes[0]['keys']),
            call(mock_indexes[1]['keys']),
        ]
        mongo_util.drop_indexes(mock_collection, mock_indexes)
        mock_collection.drop_index.assert_has_calls(calls)


class TestCreateValidator(unittest.TestCase):
    def test_create_validator_with_default(self):
        mock_collection = MagicMock()
        mock_validator = MagicMock()
        mongo_util.create_validator(mock_collection, mock_validator)
        mock_collection.database.command.assert_called_with(
            'collMod', mock_collection.name, validator=mock_validator, validationAction='error')

    def test_create_validator(self):
        mock_collection = MagicMock()
        mock_validator = MagicMock()
        mock_action = MagicMock()
        mongo_util.create_validator(mock_collection, mock_validator, action=mock_action)
        mock_collection.database.command.assert_called_with(
            'collMod', mock_collection.name, validator=mock_validator, validationAction=mock_action)
