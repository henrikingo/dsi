"""
Implementation of FixtureFiles class.
"""

import json
import os

import json_diff
import yaml


class FixtureFiles(object):
    """
    Convenience methods utilizing the fixture directory.
    """
    def __init__(self, dir_name=None, subdir_name=None, is_unittest=True):
        """
        :param directory_name: The name of the test directory. Defaults to 'tests'.
        :type directory_name: str, None.
        :param subdir_path: If the fixture files directory of interest is directory within the
        unittest-files directory, then provide the relative path.
        :type subdir_path: str, None.
        :param bool is_unittest: If true use 'unittest-files' else 'systest-files'.
        """
        dir_name = dir_name if dir_name is not None else 'bin/tests'
        subdir_name = subdir_name if subdir_name is not None else ''
        self.repo_root_dir = os.path.dirname(os.path.dirname(__file__))
        self.tests_root_dir = os.path.abspath(dir_name)
        file_path = 'unittest-files' if is_unittest else 'systest-files'
        self.fixture_dir_path = os.path.join(self.tests_root_dir, file_path, subdir_name)

    def repo_root_file_path(self, file_path):
        """
        Return the absolute path of a file at `file_path` with respect to the repo root.

        :param str file_path: The name of the file path.
        :rtype: str.
        """
        return os.path.normpath(os.path.join(self.repo_root_dir, file_path))

    def fixture_file_path(self, file_path):
        """
        Return the absolute path of a file at `file_path` with respect to the fixture directory.

        :param str file_path: The name of the file path.
        :rtype: str.
        """
        return os.path.join(self.fixture_dir_path, file_path)

    def load_json_file(self, file_path):
        """
        Convenience method to load a json file from the fixture directory.

        :param str filename: The name of the file path.
        :return: A dict representing a json file.
        """
        with open(self.fixture_file_path(file_path)) as json_file:
            return json.load(json_file)

    def load_yaml_file(self, file_path):
        """
        Convenience method to load a yaml file from the fixture directory.

        :param str filename: The name of the file path.
        :return: A dict representing a yaml file.
        """
        with open(self.fixture_file_path(file_path)) as yaml_file:
            return yaml.load(yaml_file)

    def json_files_equal(self, path1, path2):
        """
        Check whether the JSON files at paths `path1` and `path2` inside the fixture directory are
        equal.

        :param str path1: The name of a json file.
        :param str path2: The name of another json file.
        """
        json1, json2 = (self.load_json_file(path) for path in (path1, path2))
        return json1 == json2

    def yaml_files_equal(self, path1, path2):
        """
        Check whether the YAML files at paths `path1` and `path2` inside the fixture directory are
        equal.

        :param str path1: The name of a yaml file.
        :param str path2: The name of another yaml file.
        """

        yaml1, yaml2 = (self.load_yaml_file(path) for path in (path1, path2))
        return yaml1 == yaml2

    def assert_json_files_equal(self, test_case, expect, actual):
        """
        Pretty-print a json diff report if contents if expect != actual.

        :param unittest.TestCase test_case: The test case to use.
        :param IO expect: expected json file IO.
        :param IO actual: actual json file IO.
        """
        expect = self.fixture_file_path(expect)
        actual = self.fixture_file_path(actual)

        with open(expect) as file_handle_expect, open(actual) as file_handle_actual:
            diff = json_diff.Comparator(file_handle_expect, file_handle_actual)

        diff_res = diff.compare_dicts()
        outs = unicode(json_diff.HTMLFormatter(diff_res))

        with open(actual) as file_handle:
            result_perf_json = json.load(file_handle)
        with open(expect) as file_handle:
            expected_perf_json = json.load(file_handle)

        # pylint: disable=invalid-name
        test_case.maxDiff = None
        test_case.assertEqual(result_perf_json, expected_perf_json, outs)
