"""Helper functions that don't fit anywhere else"""

from ConfigParser import ConfigParser, NoOptionError
import json
import os
import re
from StringIO import StringIO

import yaml
import requests

GIT_HASH_LEN = 40
GITHUB_API = 'https://api.github.com'
GH_USER = 'mongodb'
GH_REPO = 'mongo'
GH_BASIC_AUTH = 'x-oauth-basic'


def get_evergreen_credentials(config_file='~/.evergreen.yml'):
    """Read the .evergreen.yml config file. This function raises an IOError
    if no such file is found.

    :param str config_file: used during unit testing so that comparisons do not involve
    a user's actual credentials.
    :rtype: dict
    :raises: IOError if config file not found
    :raises: KeyError if file does not contain the needed authentication information.
    """
    try:
        credentials_needed = ['user', 'api_key', 'ui_server_host']
        path_to_file = os.path.expanduser(config_file)
        evg_yml = file_as_yaml(path_to_file)
        evg_creds = {}
        for cred in credentials_needed:
            if cred in evg_yml:
                evg_creds[cred] = evg_yml[cred]
            else:
                raise KeyError('~/.evergreen.yml does not contain key {}'.format(cred))
        return evg_creds
    except IOError:
        raise IOError('No ~/.evergreen.yml file found. Please follow the instructions on '
                      'evergreen.mongodb.com/settings to permit CLI Evergreen authentication.')


def get_git_credentials(config_file='~/.gitconfig'):
    """Line-by-line parsing of the gitconfig file to retrieve the
    user authentication token.

    :param str config_file: used during unit testing so that comparisons do not involve
    a user's actual credentials.
    :rtype: dict
    :raises: NoOptionError if authentication token retrieval failed.
    """
    try:
        path_to_file = os.path.expanduser(config_file)
        with open(path_to_file) as gitconfig_handle:
            config_info = gitconfig_handle.readlines()
        parser = ConfigParser()
        # remove the tabs in a standard ~/.gitconfig, ConfigParser doesn't handle
        # the file's default formatting.
        parser.readfp(StringIO(''.join([l.lstrip() for l in config_info])))
        return {'token': parser.get('github', 'token')}
    except NoOptionError:
        raise KeyError('Could not retrieve a Github authentication token from ~/.gitconfig. See '
                       'analysis/generate_git_token.txt for instructions on adding the token to '
                       'your ~/.gitconfig.')


def create_credentials_config():
    """A method to retrieve github and evergreen credentials
    used to send authenticated API requests

    :rtype: dict
    """
    evg_creds = get_evergreen_credentials()
    github_creds = get_git_credentials()
    config = {'evergreen': evg_creds, 'github': github_creds}
    return config


def get_full_git_commit_hash(prefix, token=None):
    """Use the Github API to search for the full git commit hash
    when only the hash prefix has been submitted.

    :param str prefix: prefix for a git commit hash
    :param str token: github user authentication token
    :rtype: str
    :raises: HTTPError if retrieval of full commit hash has failed.
    """
    if len(prefix) == GIT_HASH_LEN:
        return prefix
    request = '{url}/repos/{user}/{repo}/commits/{prefix}'.format(
        url=GITHUB_API, user=GH_USER, repo=GH_REPO, prefix=prefix)
    if token is not None:
        if 'token' in token:  # sent as a header 'token: OAUTH_TOKEN'
            response = requests.get(request, headers={'Authorization': token})
        else:
            response = requests.get(request, auth=(token, GH_BASIC_AUTH))
    else:  # no authentication token
        response = requests.get(request)

    if response.ok:
        commit_info = response.json()
        return str(commit_info['sha'])
    else:
        response.raise_for_status()


def get_as_json(url, **kwargs):
    """Issue a GET request and return the response as JSON.

    :type url: str
    :param kwargs: Keyword arguments passed to `request.get()`
    :rtype: dict
    :raises: HTTPError if the response is not OK
    """
    response = requests.get(url, **kwargs)
    if not response.ok:
        response.raise_for_status()
    else:
        return response.json()


def file_as_json(file_or_filename):
    """Open a file as JSON.

    :type file_or_filename: str|file
    :rtype: dict
    """
    if isinstance(file_or_filename, file):
        return json.load(file_or_filename)
    elif isinstance(file_or_filename, str):
        with open(file_or_filename) as file_handle:
            return json.load(file_handle)
    else:
        raise TypeError('Argument must be a string or file pointer')


def file_as_yaml(file_or_filename):
    """Open a file as YAML.

    :type file_or_filename: str|file
    :rtype: dict
    """
    if isinstance(file_or_filename, file):
        return yaml.load(file_or_filename)
    elif isinstance(file_or_filename, str):
        with open(file_or_filename) as file_handle:
            return yaml.load(file_handle)
    else:
        raise TypeError('Argument must be a string or file pointer')


def matches_any(obj, patterns):
    """Determines if the object matches any of the patterns.

    :type obj: str
    :type patterns: str|list[str]
    :returns: The pattern in `patterns` that matches `obj`, or None if none of them matched
    """
    if isinstance(patterns, str):
        return re.match(patterns, obj)

    for pattern in patterns:
        if re.match(pattern, obj):
            return pattern
    return None
