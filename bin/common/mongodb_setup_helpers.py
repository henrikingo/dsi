"""
Helper functions related to mongodb_setup.
"""

from collections import namedtuple

from config import copy_obj

MongoDBAuthSettings = namedtuple('MongoDBAuthSettings', ['mongo_user', 'mongo_password'])


def mongodb_auth_configured(config):
    """Determine if authentication should be enabled.

    :param ConfigDict config: the configuration object
    :returns: True if authentication should be enabled, otherwise false
    :rtype: boolean

    """

    if 'username' in config['mongodb_setup'] and 'password' in config['mongodb_setup']:
        return True
    assert 'username' not in config['mongodb_setup'], "both username and password MUST be set"
    assert 'password' not in config['mongodb_setup'], "both username and password MUST be set"
    return False


def mongodb_auth_settings(config):
    """ Read the config file and return a tuple with the authentication settings

    :param ConfigDict config: The configuration
    :returns: The mongo user and password information
    :rtype: None or namedtuple

    """

    if not mongodb_auth_configured(config):
        return None
    return MongoDBAuthSettings(config['mongodb_setup']['username'],
                               config['mongodb_setup']['password'])


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
