"""Helper functions that don't fit anywhere else"""

from ConfigParser import ConfigParser, NoOptionError
import json
import os
import re
from StringIO import StringIO
from subprocess import Popen, PIPE

import yaml
import requests

NETWORK_TIMEOUT_SECS = 120
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
    request = '{url}/repos/{user}/{repo}/commits/{prefix}'.format(url=GITHUB_API,
                                                                  user=GH_USER,
                                                                  repo=GH_REPO,
                                                                  prefix=prefix)
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

    return response.raise_for_status()


def get_git_commits(newest, token=None, per_page=None):
    """
    Use the Github API to list commits older than newest (in descending order).

    :param str newest: The newest commit hash in the range we want to get.
    :param str token: Github user authentication token.
    :param int per_page: The max size of the page. None (the default) implies
    we use whatever github uses.
    :rtype: list(dict())
    :raises: HTTPError if retrieval of full commit hash has failed.
    """
    request = '{url}/repos/{user}/{repo}/commits?sha={sha}{per_page}'.format(
        url=GITHUB_API,
        user=GH_USER,
        repo=GH_REPO,
        sha=newest,
        per_page='' if per_page is None else '&per_page=' + str(per_page))
    if token is not None:
        if 'token' in token:  # sent as a header 'token: OAUTH_TOKEN'
            response = requests.get(request, headers={'Authorization': token})
        else:
            response = requests.get(request, auth=(token, GH_BASIC_AUTH))
    else:  # no authentication token
        response = requests.get(request)

    if response.ok:
        return response.json()
    return response.raise_for_status()


def get_githashes_in_range_github(oldest, newest, token=None, per_page=None):
    """
    Get git hashes of commits from github in descending order from newest to oldest.

    :param str newest: The git hash of the newest commit.
    :param str oldest: The git hash of the old commit.
    :param token: The git token.
    :type token: str, None.
    :param per_page: The number of hashes to get per page. None => use github default.
    :type per_page: int, None.
    :return: The git hashes between newest and oldest (from newest to oldest / descending order)
    and including newest but not oldest.
    :rtype: list(str).
    """
    commits = get_git_commits(newest, token=token, per_page=per_page)
    if newest != commits[0]['sha']:
        raise ValueError('newest {} is not in list.'.format(newest))

    index = next((i for i, item in enumerate(commits) if item['sha'] == oldest), -1)

    if index == -1:
        raise ValueError('oldest {} is not in list.'.format(oldest))
    return commits[0:index]


def get_githashes_in_range_repo(oldest, newest, mongo_repo):
    """
    Get git hashes of commits from local git repo in descending order from newest to oldest.

    It calls the following :

        $> git rev-list oldest..newest

    :param str newest: The git hash of the newest commit.
    :param str oldest: The git hash of the old commit.
    :param str mongo_repo: The mongo repo directory location.
    :return: The git hashes between newest and oldest (from newest to oldest / descending order)
    and including newest but not oldest.
    :rtype: list(str).
    """
    command = ['git', 'rev-list', '{}..{}'.format(oldest, newest)]
    process = Popen(command, stdin=PIPE, stdout=PIPE, stderr=PIPE, cwd=mongo_repo)
    output, error = process.communicate()

    if process.returncode != 0:
        raise ValueError('\'{}\' returned an error {}\n{}.'.format(' '.join(command),
                                                                   process.returncode, str(error)))
    commits = output.rstrip().split('\n')

    if newest != commits[0]:
        raise ValueError("newest '{}' is not in list.".format(newest))

    return commits


def get_as_json(url, **kwargs):
    """Issue a GET request and return the response as JSON.

    :type url: str
    :param kwargs: Keyword arguments passed to `request.get()`
    :rtype: dict
    :raises: HTTPError if the response is not OK
    """
    response = requests.get(url, timeout=NETWORK_TIMEOUT_SECS, **kwargs)
    if response.ok:
        return response.json()
    return response.raise_for_status()


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
