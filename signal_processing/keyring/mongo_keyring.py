"""
Tools for mongo access and keyring support.
"""
# pylint: disable=redefined-builtin
from builtins import input

import urllib

from getpass import getpass

from keyring.errors import PasswordSetError
from pymongo import MongoClient
from pymongo.errors import InvalidURI
from pymongo.uri_parser import parse_uri

from signal_processing.keyring.credentials import Credentials
from signal_processing.keyring.keyring_impl import Keyring

KEYRING_SERVICE_NAME = 'signal processing'
""" The keyring service name. """

KEYRING_PROPERTY_NAME = 'mongo_username_and_password'
""" The keyring property name. """


def save_credentials_to_keyring(credentials):
    """
    Store mongo credentials in keyring.

    :param credentials: credentials to store.
    """
    keyring_impl = Keyring(KEYRING_SERVICE_NAME)
    try:
        keyring_impl.write(KEYRING_PROPERTY_NAME, credentials.encode())
    except PasswordSetError as e:
        message = e.message + \
                  '''.
  You may need to codesign your python executable, refer to signal_processing/README.md.'''
        raise PasswordSetError(message)


def get_credentials_from_keyring():
    """
    Retrieve mongo credentials from keyring.

    :return: mongo credentials.
    """
    keyring_impl = Keyring(KEYRING_SERVICE_NAME)
    return Credentials.decode(keyring_impl.read(KEYRING_PROPERTY_NAME))


def prompt_for_credentials(credentials=None):
    """
    Prompt the user to enter credentials, if not provided.

    :param credentials: existing credentials.
    :return: credentials entered by user, or existing credentials..
    """
    username = None
    password = None
    if credentials is not None:
        username = credentials.username
        password = credentials.password

    if username is None:
        username = input('Mongo username: ')
    if password is None:
        password = getpass()

    return Credentials(username, password)


def new_mongo_client(mongo_uri, credentials=None, auth_type=None):
    """
    Build a new mongo client.

    :param mongo_uri: mongo instance to connect to.
    :param credentials: credentials to use to connect to db.
    :param auth_type: How is authentication information obtained..
    :return: Mongo client and credentials used to connect.
    """
    if auth_type is not None or credentials is not None:
        uri = parse_uri(mongo_uri)
        if 'password' not in uri or uri['password'] is None:
            if auth_type == 'keyring' and (credentials is None or credentials.password is None):
                credentials = get_credentials_from_keyring()

            creds = prompt_for_credentials(credentials)
            mongo_uri = add_credentials_to_uri(mongo_uri, creds)

    mongo_client = MongoClient(mongo_uri)

    return mongo_client


def add_credentials_to_uri(mongo_uri, credentials):
    """
    Create uri string to connect to mongo database.

    :param mongo_uri: mongo uri to add credentials to.
    :param credentials: credentials to add.
    :return: uri string.
    """
    if '@' in mongo_uri:
        raise InvalidURI('ERROR: Credentials provided and specified in URI')

    cred_str = '{username}:{password}@'.format(
        username=urllib.quote_plus(credentials.username),
        password=urllib.quote_plus(credentials.password))

    uri_list = mongo_uri.split('//')
    uri_list.insert(1, '//')
    uri_list.insert(2, cred_str)

    return ''.join(uri_list)
