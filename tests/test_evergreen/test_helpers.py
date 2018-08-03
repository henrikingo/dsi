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
        # Real commit data from master.
        self.newest = 'af600c3876a26f62d8dde93bf769fc4ca3054072'
        self.oldest = '59a4bf14617facbb49520e00c91a55ac8e9a316c'
        self.expected = [
            'af600c3876a26f62d8dde93bf769fc4ca3054072', '2676a176759359c8614c0e37b267198259b6789f',
            'b3c9e24d7434c929c097d85f65a3586687031116', 'cee356dbc43d4836594fa517a383fa6ac66f735a',
            '33f5cf3c7eb4e260b8cafa218bc99cf736dcbc63', '985506c410db79d3a576e5c6b088a8f43ed15da7',
            '607f306f614ad7ecaba3c72bd99bb661242187ef', '9b6bcfd63f9413caaa2fdd12e9dedb712ca66913',
            '36148ad8bbdb94162b2926f4700d935ee4dc5994', 'd62d631f0ca40c5199fdfae2980080ca0cc982b5'
        ]
        self.return_value = [{
            'sha': sha
        } for sha in self.expected + ['59a4bf14617facbb49520e00c91a55ac8e9a316c']]

    @patch('evergreen.helpers.get_git_commits')
    def test_get_githashes_in_range_github(self, mock_get):
        """
        Test getting 10 git commits in range.
        """
        mock_get.return_value = self.return_value
        actual = helpers.get_githashes_in_range_github(self.oldest, self.newest)
        shas = [commit['sha'] for commit in actual]
        self.assertEqual(shas, self.expected)
        mock_get.assert_called_once_with(self.expected[0], token=None, per_page=None)

    @patch('evergreen.helpers.get_git_commits')
    def test_get_githashes_in_range_github_lower_bounds_error(self, mock_get):
        """
        Test getting commit with error in lower bound.
        """
        mock_get.return_value = self.return_value

        with self.assertRaises(ValueError) as exception:
            helpers.get_githashes_in_range_github('old', 'new')

        self.assertEqual(str(exception.exception), 'newest new is not in list.')

    @patch('evergreen.helpers.get_git_commits')
    def test_get_githashes_in_range_github_upper_bounds_error(self, mock_get):
        """
        Test getting commit with error in upper.
        """
        mock_get.return_value = self.return_value

        with self.assertRaises(ValueError) as exception:
            helpers.get_githashes_in_range_github('old', self.expected[0])

        self.assertEqual(str(exception.exception), 'oldest old is not in list.')


# pylint: disable=invalid-name
class TestGetRevList(unittest.TestCase):
    """
    Test get_githashes_in_range_repo.
    """

    def setUp(self):
        # Real commit data from master.
        self.newest = 'af600c3876a26f62d8dde93bf769fc4ca3054072'
        self.oldest = '59a4bf14617facbb49520e00c91a55ac8e9a316c'
        self.expected = [
            'af600c3876a26f62d8dde93bf769fc4ca3054072', '2676a176759359c8614c0e37b267198259b6789f',
            'b3c9e24d7434c929c097d85f65a3586687031116', 'cee356dbc43d4836594fa517a383fa6ac66f735a',
            '33f5cf3c7eb4e260b8cafa218bc99cf736dcbc63', '985506c410db79d3a576e5c6b088a8f43ed15da7',
            '607f306f614ad7ecaba3c72bd99bb661242187ef', '9b6bcfd63f9413caaa2fdd12e9dedb712ca66913',
            '36148ad8bbdb94162b2926f4700d935ee4dc5994', 'd62d631f0ca40c5199fdfae2980080ca0cc982b5'
        ]
        self.return_value = [{
            'sha': sha
        } for sha in self.expected + ['59a4bf14617facbb49520e00c91a55ac8e9a316c']]

    @patch('evergreen.helpers.Popen')
    def test_get_githashes_in_range_repo(self, mock_popen):
        """
        Test no error.
        """
        mock_process = MagicMock(name='process', returncode=0)
        mock_process.communicate.return_value = ("\n".join(self.expected) + "\n", 'error')
        mock_popen.return_value = mock_process
        actual = helpers.get_githashes_in_range_repo(self.oldest, self.newest, 'repo')
        self.assertEqual(actual, self.expected)
        mock_popen.assert_called_once_with(
            ['git', 'rev-list', self.oldest + '..' + self.newest],
            stdin=PIPE,
            stdout=PIPE,
            stderr=PIPE,
            cwd='repo')

    @patch('evergreen.helpers.Popen')
    def test_get_githashes_in_range_repo_error(self, mock_popen):
        """
        Test process error.
        """
        mock_process = MagicMock(name='process', returncode=1)
        mock_process.communicate.return_value = ("\n".join(self.expected) + "\n", 'error')
        mock_popen.return_value = mock_process
        with self.assertRaises(ValueError) as exception:
            helpers.get_githashes_in_range_repo(self.oldest, self.newest, 'repo')
        expected = """'git rev-list {}..{}' returned an error 1\nerror.""".format(
            self.oldest, self.newest)
        self.assertEqual(str(exception.exception), expected)

    @patch('evergreen.helpers.Popen')
    def test_get_githashes_in_range_repo_newest_error(self, mock_popen):
        """
        Test newest error.
        """
        mock_process = MagicMock(name='process', returncode=0)
        mock_process.communicate.return_value = ("sha\nolder\n", 'error')
        mock_popen.return_value = mock_process
        with self.assertRaises(ValueError) as exception:
            helpers.get_githashes_in_range_repo(self.oldest, self.newest, 'repo')
        expected = "newest '{}' is not in list.".format(self.newest)
        self.assertEqual(str(exception.exception), expected)

    # def test_get_githashes_in_range_repo_newest_real(self):
    #     """ Test on real repo. Assuming it is in ~/src """
    #     actual = helpers.get_githashes_in_range_repo(self.oldest, self.newest, '/home/jim/src')
    #     self.assertEqual(actual, self.expected)
