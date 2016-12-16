"""Miscellaneous utility functions used by the unit tests."""

import os
import contextlib
import sys
import yaml

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
