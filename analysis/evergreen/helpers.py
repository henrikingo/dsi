# Copyright 2015 MongoDB Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Helper functions that don't fit anywhere else"""

import json
import re

import yaml
import requests


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
        with open(file_or_filename) as file_ptr:
            return json.load(file_ptr)
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
        with open(file_or_filename) as file_ptr:
            return yaml.load(file_ptr)
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
