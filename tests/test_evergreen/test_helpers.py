"""Unit tests for evergreen.helper functions. Using nosetest, run from dsi directory."""
import platform
import unittest
from subprocess import PIPE

import requests

from evergreen import helpers
from mock import patch, MagicMock

from analysis.evergreen.helpers import GITHUB_API
from tests import test_utils


class TestEvergreenHelpers(unittest.TestCase):
    """Tests are related to Evergreen & Github API access"""

    def setUp(self):
        """Specify the expected result variables used in more than 1 test"""
        config_file = test_utils.repo_root_file_path('config.yml')

        self.expected_evergreen = {
            'user': 'username',
            'api_key': 'api_key_here',
            'ui_server_host': 'https://evergreen.mongodb.com'
        }
        self.expected_git = {'token': 'token_here'}
        self.expected_full_hash = 'c2af7abae8d09d290d7457ab77f5a7529806b75a'

        self.creds = helpers.file_as_yaml(config_file)

    def test_evg_creds_success(self):
        """Test a valid Evergreen config file"""
        config_file = test_utils.fixture_file_path('evergreen/test_helpers/valid_evergreen.yml')
        evg_creds = helpers.get_evergreen_credentials(config_file=config_file)
        self.assertEqual(evg_creds, self.expected_evergreen)

    def test_evg_creds_missing_file(self):
        """Test for a missing Evergreen config file"""
        with self.assertRaises(IOError):
            helpers.get_evergreen_credentials('~/.notavalidfile')

    def test_git_creds_success(self):
        """Test a valid .gitconfig file (containing a user authentication token)"""
        config_file = test_utils.fixture_file_path('evergreen/test_helpers/valid_gitconfig')
        gh_creds = helpers.get_git_credentials(config_file=config_file)
        self.assertEqual(gh_creds, self.expected_git)

    def test_git_creds_missing_file(self):
        """Test for a missing .gitconfig file"""
        with self.assertRaises(IOError):
            helpers.get_git_credentials('~/.notavalidfile')

    def test_git_creds_token_not_found(self):
        """Test a valid .gitconfig file that does not contain an authentication token"""
        config_file = test_utils.fixture_file_path('evergreen/test_helpers/valid_gitconfig_notoken')
        with self.assertRaises(KeyError):
            helpers.get_git_credentials(config_file)

    def test_git_hash_full(self):
        """Test for an input that is already a full git hash"""
        retrieved = helpers.get_full_git_commit_hash(self.expected_full_hash,
                                                     self.creds['github']['token'])
        self.assertEqual(retrieved, self.expected_full_hash)

    def test_git_hash_success(self):
        """Test for an input that is a prefix of a valid git hash"""
        retrieved = helpers.get_full_git_commit_hash(self.expected_full_hash[:8],
                                                     self.creds['github']['token'])
        self.assertEqual(retrieved, self.expected_full_hash)

    @unittest.skipIf('darwin' in platform.system().lower(), "evergreen osx runners fail, PERF-1363")
    def test_git_hash_error(self):
        """Test for an input that is an invalid hash"""
        with self.assertRaises(requests.exceptions.HTTPError):
            helpers.get_full_git_commit_hash('invalid_hash', self.creds['github']['token'])


class TestGitCommit(unittest.TestCase):
    """
    Test get_git_commits.
    """

    def setUp(self):
        self.url = '{}/repos/mongodb/mongo/commits'.format(GITHUB_API)

    @patch('evergreen.helpers.requests')
    def test_get_git_commits(self, mock_requests):
        """
        Test getting 3 git commits.
        """
        mock_response = MagicMock(name='response', ok=True)
        mock_requests.get.return_value = mock_response
        helpers.get_git_commits('sha')
        mock_requests.get.assert_called_with(self.url + '?sha=sha')
        mock_response.json.assert_called_once()

    @patch('evergreen.helpers.requests')
    def test_get_git_commits_per_page(self, mock_requests):
        """
        Test getting 3 git commits.
        """
        mock_response = MagicMock(name='response', ok=True)
        mock_requests.get.return_value = mock_response
        helpers.get_git_commits('sha', per_page=1)
        mock_requests.get.assert_called_with(self.url + '?sha=sha&per_page=1')
        mock_response.json.assert_called_once()

    @patch('evergreen.helpers.requests')
    def test_get_git_commits_not_ok(self, mock_requests):
        """
        Test getting 3 git commits.
        """
        mock_response = MagicMock(name='response', ok=False)
        mock_requests.get.return_value = mock_response
        helpers.get_git_commits('sha')
        mock_requests.get.assert_called_with(self.url + '?sha=sha')
        mock_response.raise_for_status.assert_called_once()


# pylint: disable=invalid-name
class TestGetGithashes(unittest.TestCase):
    """
    Test get_githashes_in_range_github.
    """

    def setUp(self):
        self.expected = [
            '4cdaee88d7122f3ccba152ae37d3b5b69b3b398f', '472d4ecaf989b239e324ef12b39357802d96f607',
            '461184c1467fb6c130638b27bf1d71962c7e830b'
        ]
        self.return_value = [{'sha': sha} for sha in self.expected]

    @patch('evergreen.helpers.get_git_commits')
    def test_get_githashes_in_range_github(self, mock_get):
        """
        Test getting 3 git commits in range.
        """
        mock_get.return_value = self.return_value
        actual = helpers.get_githashes_in_range_github(self.expected[0], self.expected[-1])
        self.assertEqual([commit['sha'] for commit in actual], self.expected)
        mock_get.assert_called_once_with(self.expected[0], token=None, per_page=None)

    @patch('evergreen.helpers.get_git_commits')
    def test_get_githashes_in_range_github_lower_bounds_error(self, mock_get):
        """
        Test getting commit with error in lower bound.
        """
        mock_get.return_value = self.return_value

        with self.assertRaises(ValueError) as exception:
            helpers.get_githashes_in_range_github('new', 'old')

        self.assertEqual(str(exception.exception), 'newest new is not in list.')

    @patch('evergreen.helpers.get_git_commits')
    def test_get_githashes_in_range_github_upper_bounds_error(self, mock_get):
        """
        Test getting commit with error in upper.
        """
        mock_get.return_value = self.return_value

        with self.assertRaises(ValueError) as exception:
            helpers.get_githashes_in_range_github(self.expected[0], 'old')

        self.assertEqual(str(exception.exception), 'oldest old is not in list.')


# pylint: disable=invalid-name
class TestGetRevList(unittest.TestCase):
    """
    Test get_githashes_in_range_repo.
    """

    @patch('evergreen.helpers.Popen')
    def test_get_githashes_in_range_repo_error(self, mock_popen):
        """
        Test process error.
        """
        mock_process = MagicMock(name='process', returncode=1)
        mock_process.communicate.return_value = ("newest\nolder\n", 'error')
        mock_popen.return_value = mock_process
        with self.assertRaises(ValueError) as exception:
            helpers.get_githashes_in_range_repo('newest', 'oldest', 'repo')
        expected = """'git rev-list oldest..newest' returned an error 1\nerror."""
        self.assertEqual(str(exception.exception), expected)

    @patch('evergreen.helpers.Popen')
    def test_get_githashes_in_range_repo(self, mock_popen):
        """
        Test no error.
        """
        mock_process = MagicMock(name='process', returncode=0)
        mock_process.communicate.return_value = ("newest\nolder\n", 'error')
        mock_popen.return_value = mock_process
        actual = helpers.get_githashes_in_range_repo('newest', 'oldest', 'repo')
        expected = ['newest', 'older', 'oldest']
        self.assertEqual(actual, expected)
        mock_popen.assert_called_once_with(
            ['git', 'rev-list', 'oldest..newest'], stdin=PIPE, stdout=PIPE, stderr=PIPE, cwd='repo')

    @patch('evergreen.helpers.Popen')
    def test_get_githashes_in_range_repo_newest_error(self, mock_popen):
        """
        Test no error.
        """
        mock_process = MagicMock(name='process', returncode=0)
        mock_process.communicate.return_value = ("sha\nolder\n", 'error')
        mock_popen.return_value = mock_process
        with self.assertRaises(ValueError) as exception:
            helpers.get_githashes_in_range_repo('newest', 'oldest', 'repo')
        expected = "newest 'newest' is not in list."
        self.assertEqual(str(exception.exception), expected)
