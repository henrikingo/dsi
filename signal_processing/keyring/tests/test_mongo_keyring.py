"""
Unit tests for signal_processing/keyring/mongo_keyring.py
"""
import unittest

from mock import patch

from pymongo.errors import InvalidURI

from signal_processing.keyring.credentials import Credentials
from signal_processing.keyring.mongo_keyring import new_mongo_client, add_credentials_to_uri

NS = 'signal_processing.keyring.mongo_keyring'


def ns(relative_name):  # pylint: disable=invalid-name
    """Return a full name from a name relative to the tested module's name space."""
    return NS + '.' + relative_name


class TestMongoKeyring(unittest.TestCase):
    @patch(ns('MongoClient'))
    def test_new_mongo_client_no_auth(self, mongo_client_mock):
        client_mock = new_mongo_client('mongodb://mongo_uri')

        self.assertEqual(mongo_client_mock.return_value, client_mock)

    @patch(ns('MongoClient'))
    def test_new_mongo_client_with_credentials(self, mongo_client_mock):
        credentials = Credentials('user', 'password')
        client_mock = new_mongo_client('mongodb://mongo_uri', credentials=credentials)

        self.assertEqual(client_mock, mongo_client_mock.return_value)
        mongo_client_mock.assert_called_with('mongodb://user:password@mongo_uri')

    @patch(ns('input'))
    @patch(ns('getpass'))
    @patch(ns('MongoClient'))
    def test_new_mongo_client_with_prompts(self, mongo_client_mock, getpass_mock, input_mock):
        input_mock.return_value = 'user'
        getpass_mock.return_value = 'password'
        client_mock = new_mongo_client('mongodb://mongo_uri', auth_type='prompt')

        self.assertEqual(client_mock, mongo_client_mock.return_value)
        mongo_client_mock.assert_called_with('mongodb://user:password@mongo_uri')

    @patch(ns('get_credentials_from_keyring'))
    @patch(ns('MongoClient'))
    def test_new_mongo_client_with_keyring(self, mongo_client_mock, get_creds_mock):
        get_creds_mock.return_value = Credentials('user', 'password')
        client_mock = new_mongo_client('mongodb://mongo_uri', auth_type='keyring')

        self.assertEqual(client_mock, mongo_client_mock.return_value)
        mongo_client_mock.assert_called_with('mongodb://user:password@mongo_uri')

    def test_add_credentials_to_uri(self):
        original_uri = 'mongodb://host:27017/perf'
        user = 'username'
        password = 'password'

        self.assertEqual('mongodb://username:password@host:27017/perf',
                         add_credentials_to_uri(original_uri, Credentials(user, password)))

    def test_add_credentials_to_uri_with_srv(self):
        original_uri = 'mongodb+srv://host:27017/perf'
        user = 'username'
        password = 'password'

        self.assertEqual('mongodb+srv://username:password@host:27017/perf',
                         add_credentials_to_uri(original_uri, Credentials(user, password)))

    def test_add_credentials_with_creds_already_in_uri(self):
        original_uri = 'mongodb+srv://user:password@host:27017/perf'
        user = 'username'
        password = 'password'

        with self.assertRaises(InvalidURI):
            add_credentials_to_uri(original_uri, Credentials(user, password))

    def test_add_credentials_with_user_already_in_uri(self):
        original_uri = 'mongodb+srv://user@host:27017/perf'
        user = 'username'
        password = 'password'

        with self.assertRaises(InvalidURI):
            add_credentials_to_uri(original_uri, Credentials(user, password))
