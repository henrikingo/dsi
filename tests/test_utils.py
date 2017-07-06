"""Miscellaneous utility functions used by the unit tests."""

import os
import contextlib
import sys
import shelve
import yaml
import requests

import util


# Useful absolute directory paths.
TESTS_ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT_DIR = os.path.normpath(os.path.join(TESTS_ROOT_DIR, ".."))
FIXTURE_DIR_PATH = os.path.join(TESTS_ROOT_DIR, "unittest-files/")

def repo_root_file_path(file_path):
    """"Return the absolute path of a file at `file_path` with respect to the repo root."""

    return os.path.normpath(os.path.join(REPO_ROOT_DIR, file_path))

def fixture_file_path(file_path):
    """Return the absolute path of a file at `file_path` inside the fixture files directory."""

    return os.path.join(FIXTURE_DIR_PATH, file_path)

def get_yaml(filename):
    """ Load a file and parse it as yaml """
    with open(filename) as yaml_file:
        return yaml.load(yaml_file)

def read_fixture_yaml_file(file_path):
    """Return the yaml data from the file at `file_path` inside the fixtures files directory. """

    return get_yaml(fixture_file_path(file_path))

def read_fixture_json_file(file_path):
    """Return the JSON data from the file at `file_path` inside the fixtures files directory. """

    return util.get_json(fixture_file_path(file_path))

def eq_fixture_json_files(path1, path2):
    """
    Check whether the JSON files at paths `path1` and `path2` inside the fixtures directory are
    equal.
    """

    json1, json2 = (util.get_json(fixture_file_path(path)) for path in (path1, path2))
    return json1 == json2

def eq_fixture_yaml_files(path1, path2):
    """
    Check whether the YAML files at paths `path1` and `path2` inside the fixtures directory are
    equal.
    """

    yaml1, yaml2 = (get_yaml(fixture_file_path(path)) for path in (path1, path2))
    return yaml1 == yaml2

@contextlib.contextmanager
def redirect_stdout(file_handle):
    """
    A context manager for temporarily redirecting the program's `stdout` output to `file_handle`.
    """

    normal_stdout = sys.stdout
    sys.stdout = file_handle
    exception = None
    try:
        yield
    except Exception as exception: # pylint: disable=broad-except
        pass
    sys.stdout = normal_stdout
    if exception is not None:
        raise exception # pylint: disable=raising-bad-type

class ContextShelve(object):
    """
    ContextShelve is essentially a wrapper around shelve.
    Necessary because shelve does not have a context manager
    in Python 2.7 and because get() needed to take in
    dumby **kwargs for mocking on get_as_json
    """
    def __init__(self, filename, flag='c', protocol=None, writeback=False):
        """Create a new ContextShelve
        Essentially a copy of shelve.open except it args are saved during construction
        Refer to:
        https://docs.python.org/2/library/shelve.html#shelve.open
        """
        self.filename = filename
        self.flag = flag
        self.protocol = protocol
        self.writeback = writeback
        self.dictionary = None

    def __enter__(self):
        """
        Enters the context. Opens the persistent dictionary using shelve.
        """
        self.open()
        return self

    def open(self):
        """
        Opens the persistent dictionary using shelve.
        """
        self.dictionary = shelve.open(self.filename, self.flag, self.protocol, self.writeback)

    def get(self, url, **kwargs):
        """
        A wrapper around shelve.get(). If the key is not in the dictionary,
        does a get request to get the data and updated the dictionary
        :param url string: Key used to access value in self.dictionary
        :param **kwargs: Dummy arguments necessary for mocking get_as_json
        """
        if not self.dictionary.has_key(url):
            response = requests.get(url, **kwargs)
            self.dictionary[url] = response.json()
        return self.dictionary.get(url)

    def close(self):
        """
        A wrapper around shelve.close().
        Closes self.dictionary and sets it to None
        """
        self.dictionary.close()
        self.dictionary = None

    def __exit__(self, *args):
        self.close()
