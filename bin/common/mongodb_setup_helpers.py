"""
Helper functions related to mongodb_setup.
"""

from collections import namedtuple

from config import copy_obj

MongoDBAuthSettings = namedtuple('MongoDBAuthSettings', ['mongo_user', 'mongo_password'])


def mongodb_auth_configured(config):
    """
    Determine if authentication should be enabled.

    :param ConfigDict config: The configuration object.
    :returns: True if authentication should be enabled, otherwise false.
    :rtype: boolean.
    """

    if config['bootstrap']['authentication'] == 'disabled':
        return False
    auth_config = config['mongodb_setup']['authentication']['enabled']
    assert 'username' in auth_config, 'both username and password MUST be set'
    assert 'password' in auth_config, 'both username and password MUST be set'
    return True


def mongodb_auth_settings(config):
    """
    Read the config file and return a namedtuple with the authentication settings.

    :param ConfigDict config: The configuration.
    :returns: The mongo user and password information.
    :rtype: None or namedtuple.
    """

    if not mongodb_auth_configured(config):
        return None
    return MongoDBAuthSettings(config['mongodb_setup']['authentication']['enabled']['username'],
                               config['mongodb_setup']['authentication']['enabled']['password'])


def merge_dicts(base, override):
    """
    Recursively merges nested dictionaries.

    We use this in MongodbSetup to merge a ConfigDict and a dict, and return a dict.
    """
    copy = copy_obj(base)
    # update takes care of overriding non-dict values
    copy.update(override)
    for key in copy:
        if key in base and isinstance(copy[key], dict) and isinstance(base[key], dict):
            copy[key] = merge_dicts(base[key], copy[key])
    return copy
