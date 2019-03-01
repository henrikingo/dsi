"""
Helper functions related to mongodb_setup.
"""

from collections import namedtuple

import jinja2

from config import copy_obj

MongoDBAuthSettings = namedtuple('MongoDBAuthSettings', ['mongo_user', 'mongo_password'])


def mongodb_auth_configured(config):
    """
    Determine if authentication should be enabled.

    :param ConfigDict config: The configuration object.
    :returns: True if authentication should be enabled, otherwise false.
    :rtype: boolean.
    """

    return config['mongodb_setup']['authentication']['enabled']


def mongodb_auth_settings(config):
    """
    Read the config file and return a namedtuple with the authentication settings.

    :param ConfigDict config: The configuration.
    :returns: The mongo user and password information.
    :rtype: MongoDBAuthSettings.
    """

    if not mongodb_auth_configured(config):
        return None
    return MongoDBAuthSettings(config['mongodb_setup']['authentication']['username'],
                               config['mongodb_setup']['authentication']['password'])


def add_user(cluster, config, write_concern=1):
    """
    Database command to add a root user to the given cluster. The username and password of the user
    are found in the config file.

    :param MongoCluster cluster: The cluster to which the user will be added.
    :param int write_concern: The number of nodes in the cluster that should acknowlege write
    operations requested by the client. The default is 1.
    """
    script_template = jinja2.Template('''
        db.getSiblingDB("admin").createUser(
          {
            user: {{user|tojson}},
            pwd: {{password|tojson}},
            roles: [ { role: "root", db: "admin" } ]
          },
          {
            w: {{wc|tojson}},
            wtimeout: 10000
          });''')

    add_user_script = script_template.render(
        user=config['mongodb_setup']['authentication']['username'],
        password=config['mongodb_setup']['authentication']['password'],
        wc=write_concern)
    cluster.run_mongo_shell(add_user_script)


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
