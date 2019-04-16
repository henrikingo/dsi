"""
Unit tests for signal_processing/model/configuration.py.
"""

import os
import random
import unittest
from collections import OrderedDict

from mock import MagicMock, patch

from signal_processing.change_points.e_divisive import deterministic_random
from signal_processing.model.configuration import flatten, ConfigurationModel, KEYS, \
    DEFAULT_CONFIG, VALIDATION_KEYS, validate_configuration
from signal_processing.tests.helpers import Helpers
from test_lib.fixture_files import FixtureFiles

FIXTURE_FILES = FixtureFiles(os.path.dirname(__file__))

NS = 'signal_processing.model.configuration'


def ns(relative_name):  # pylint: disable=invalid-name
    """Return a full name from a name relative to the tested module's name space."""
    return NS + '.' + relative_name


class TestValidateConfiguration(unittest.TestCase):
    """
    Test suite for validate_configuration.
    """

    def _test(self, expected=None, to_remove=None, configuration=None):
        if expected is None:
            expected = VALIDATION_KEYS[:]
        if to_remove is None:
            to_remove = []
        test_identifier = Helpers.create_test_identifier()
        for key in to_remove:
            del test_identifier[key]
        if configuration is None:
            configuration = DEFAULT_CONFIG._asdict()
        actual = validate_configuration(test_identifier, configuration)
        self.assertListEqual(sorted(expected), sorted(actual))

    def test_invalid_to_thread_level(self):
        self._test()

    def test_invalid_to_test(self):
        self._test(to_remove=['thread_level'])

    def test_valid_to_task(self):
        self._test(expected=[], to_remove=['test', 'thread_level'])

    def test_valid_to_task(self):
        self._test(expected=[], to_remove=['test', 'thread_level'])

    def test_random_invalid(self):
        with deterministic_random(3.1415):
            keys = VALIDATION_KEYS[:]
            random.shuffle(keys)
            pos = len(keys) / 2
            to_remove = keys[:pos]
            to_keep = keys[pos:]
            configuration = DEFAULT_CONFIG._asdict()
            for key in to_remove:
                del configuration[key]

        self._test(expected=to_keep, configuration=configuration)


class TestFlatten(unittest.TestCase):
    """
    Test suite for flatten.
    """

    def test(self):
        configuration = {'find': 'me'}
        result = flatten(configuration)
        self.assertEquals([(('find', ), 'me')], result)

    def test_multi(self):
        configuration = {'first': {'second': 'me', 'third': 'you'}}
        result = flatten(configuration)
        self.assertEquals([(('first', 'second'), 'me'), (('first', 'third'), 'you')], result)

    def test_prefix(self):
        configuration = {'first': {'second': 'me', 'third': 'you'}}
        result = flatten(configuration, prefix=('configuration', ))
        self.assertEquals([(('configuration', 'first', 'second'), 'me'),
                           (('configuration', 'first', 'third'), 'you')], result)

    def test_str_prefix(self):
        configuration = {'first': {'second': 'me', 'third': 'you'}}
        result = flatten(configuration, prefix='configuration')
        self.assertEquals([(('configuration', 'first', 'second'), 'me'),
                           (('configuration', 'first', 'third'), 'you')], result)

    def test_none_prefix(self):
        configuration = {'first': {'second': 'me', 'third': 'you'}}
        result = flatten(configuration, prefix=None)
        self.assertEquals([(('first', 'second'), 'me'), (('first', 'third'), 'you')], result)

    def test_tuple_prefix(self):
        configuration = {'first': {'second': 'me', 'third': 'you'}}
        result = flatten(configuration, prefix=())
        self.assertEquals([(('first', 'second'), 'me'), (('first', 'third'), 'you')], result)

    def test_empty_list_prefix(self):
        configuration = {'first': {'second': 'me', 'third': 'you'}}
        result = flatten(configuration, prefix=[])
        self.assertEquals([(('first', 'second'), 'me'), (('first', 'third'), 'you')], result)

    def test_empty_str_prefix(self):
        configuration = {'first': {'second': 'me', 'third': 'you'}}
        result = flatten(configuration, prefix='')
        self.assertEquals([(('first', 'second'), 'me'), (('first', 'third'), 'you')], result)


class TestConfigurationModel(unittest.TestCase):
    """
    Test suite for the ConfigurationModel class.
    """

    def test_ctor(self):
        """ test for ctor. """
        mongo_uri = 'uri'
        model = ConfigurationModel(mongo_uri)
        self.assertEquals(model.mongo_uri, mongo_uri)
        self.assertIsNone(model._db)
        self.assertIsNone(model._collection)
        self.assertEquals(model.__getstate__(), {'mongo_uri': mongo_uri})

    def test_db(self):
        """ test for db property. """
        mongo_uri = 'uri'
        model = ConfigurationModel(mongo_uri)
        mock_db = MagicMock(name='database')
        mock_mongo = MagicMock(name='MongoClient')
        mock_mongo.get_database.return_value = mock_db
        with (patch(ns('pymongo.MongoClient'))) as mock_mongo_cls:
            mock_mongo_cls.return_value = mock_mongo
            self.assertEquals(model.db, mock_db)
            self.assertEquals(model.db, mock_db)
        mock_mongo_cls.assert_called_once_with(mongo_uri)

    def test_collection(self):
        """ test for db collection. """
        mongo_uri = 'uri'
        mock_collection = MagicMock(name='collection')
        model = ConfigurationModel(mongo_uri)
        model._db = MagicMock(name='database', configuration=mock_collection)
        self.assertEquals(model.collection, mock_collection)


class TestGetConfiguration(unittest.TestCase):
    """
    Test suite for the ConfigurationModel.get_configuration.
    """

    def _test_get_configuration_none(self, return_value=None):
        """ test for get_configuration. """
        mongo_uri = 'uri'
        mock_collection = MagicMock(name='collection')
        model = ConfigurationModel(mongo_uri)
        model._collection = mock_collection

        test_identifier = Helpers.create_test_identifier()
        if return_value:
            mock_collection.find_one.side_effect = return_value
        else:
            mock_collection.find_one.return_value = return_value

        return model.get_configuration(test_identifier)

    def test_get_configuration_none(self):
        """ test for get_configuration returns none. """
        expected = []
        actual = self._test_get_configuration_none()
        self.assertListEqual(actual, expected)

    def test_get_configuration_empty(self):
        """ test for get_configuration returns empty list. """
        expected = []
        actual = self._test_get_configuration_none(return_value=[])
        self.assertListEqual(actual, expected)

    def test_get_configuration(self):
        """ test for get_configuration returns result. """
        return_value = [
            'project result', 'variant result', 'task result', 'test result', 'thread level result'
        ]
        expected = list(reversed(return_value))
        actual = self._test_get_configuration_none(return_value=return_value)
        self.assertListEqual(actual, expected)

    def test_get_configuration_with_nones(self):
        """ test for get_configuration returns result. """
        return_value = ['project result', None, 'task result', None, 'thread level result']
        expected = list(reversed([result for result in return_value if result is not None]))
        actual = self._test_get_configuration_none(return_value=return_value)
        self.assertListEqual(actual, expected)


class TestSetConfiguration(unittest.TestCase):
    """
    Test suite for the ConfigurationModel.set_configuration.
    """

    def test_get_configuration_none(self):
        """ test for get_configuration returns none. """

        mongo_uri = 'uri'
        mock_collection = MagicMock(name='collection')
        model = ConfigurationModel(mongo_uri)
        model._collection = mock_collection

        test_identifier = Helpers.create_test_identifier()
        mock_collection.update_one.return_value = 'return_value'

        on_insert = {'_id': OrderedDict([(key, test_identifier[key]) for key in KEYS])}
        configuration = {'update1': '1', 'update2': '2'}
        update = {
            '$set': {
                'configuration.update1': '1',
                'configuration.update2': '2'
            },
            '$setOnInsert': on_insert
        }
        self.assertEquals(model.set_configuration(test_identifier, configuration), 'return_value')
        mock_collection.update_one.assert_called_once_with(test_identifier, update, upsert=True)


class TestDeleteConfiguration(unittest.TestCase):
    """
    Test suite for the ConfigurationModel.delete_configuration.
    """

    def test_get_configuration_none(self):
        """ test for get_configuration returns none. """

        mongo_uri = 'uri'
        mock_collection = MagicMock(name='collection')
        model = ConfigurationModel(mongo_uri)
        model._collection = mock_collection

        test_identifier = Helpers.create_test_identifier()
        mock_collection.delete_one.return_value = 'return_value'

        self.assertEquals(model.delete_configuration(test_identifier), 'return_value')
        mock_collection.delete_one.assert_called_once_with(test_identifier)
