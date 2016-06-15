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

"""Unit tests for evergreen.helper functions. nosetests: run from dsi or dsi/analysis."""

import os
import unittest

from evergreen import helpers  # pylint: disable=import-error


class TestEvergreenHelpers(unittest.TestCase):
    """Tests are related to Evergreen & Github API access"""

    def setUp(self):
        """Specify the expected result variables used in more than 1 test"""
        self.expected_evergreen = {'user': 'username',
                                   'api_key': 'api_key_here',
                                   'ui_server_host': 'https://evergreen.mongodb.com'}
        self.expected_git = {'token': 'token_here'}
        self.expected_full_hash = 'c2af7abae8d09d290d7457ab77f5a7529806b75a'
        abs_path = os.path.dirname(os.path.abspath(__file__))
        self.file_path_prefix = os.path.join(abs_path, 'unittest-files')

    def test_evg_creds_success(self):
        """Test a valid Evergreen config file"""
        config_file = os.path.join(self.file_path_prefix, 'valid_evergreen.yml')
        evg_creds = helpers.get_evergreen_credentials(
            config_file=config_file)
        self.assertEqual(evg_creds, self.expected_evergreen)

    def test_evg_creds_missing_file(self):
        """Test for a missing Evergreen config file"""
        with self.assertRaises(IOError):
            helpers.get_evergreen_credentials('~/.notavalidfile')

    def test_git_creds_success(self):
        """Test a valid .gitconfig file (containing a user authentication token)"""
        config_file = os.path.join(self.file_path_prefix, 'valid_gitconfig')
        gh_creds = helpers.get_git_credentials(config_file=config_file)
        self.assertEqual(gh_creds, self.expected_git)

    def test_git_creds_missing_file(self):
        """Test for a missing .gitconfig file"""
        with self.assertRaises(IOError):
            helpers.get_git_credentials('~/.notavalidfile')

    def test_git_creds_token_not_found(self):
        """Test a valid .gitconfig file that does not contain an authentication token"""
        config_file = os.path.join(self.file_path_prefix, 'valid_gitconfig_notoken')
        with self.assertRaises(KeyError):
            helpers.get_git_credentials(config_file)

    def test_git_hash_full(self):
        """Test for an input that is already a full git hash"""
        retrieved = helpers.get_full_git_commit_hash(self.expected_full_hash)
        self.assertEqual(retrieved, self.expected_full_hash)

    def test_git_hash_success(self):
        """Test for an input that is a prefix of a valid git hash"""
        retrieved = helpers.get_full_git_commit_hash(self.expected_full_hash[:7])
        self.assertEqual(retrieved, self.expected_full_hash)

    def test_git_hash_error(self):
        """Test for an input that is an invalid hash"""
        import requests
        with self.assertRaises(requests.exceptions.HTTPError):
            helpers.get_full_git_commit_hash('invalid_hash')

if __name__ == '__main__':
    unittest.main()
