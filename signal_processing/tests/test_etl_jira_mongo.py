"""
Unit tests for signal_processing/etl_jira_mongo.py.
"""

from collections import OrderedDict
import unittest

from click.testing import CliRunner
from mock import MagicMock, patch

from signal_processing import etl_jira_mongo
from signal_processing.etl_jira_mongo import EtlJira, main


class MockJiraIssue(object):
    """
    A mock issue as returned by Jira.
    """

    def __init__(self, key):
        class MockFields(object):
            def __init__(self):
                self.summary = "This is a fake Jira issue."
                self.status = "Resolved"
                self.custom_field = ["Value 1", "Value 2"]

        self.key = key
        self.fields = MockFields()


class MockJiraClass(object):
    """
    A simple mock Jira class.
    """

    def search_issues(self, jql, maxResults=50):  # pylint: disable=invalid-name
        """
        Mock implementation of Jira.search_issues().

        :return: A list with 2 MockJiraIssue instances
        """
        return [MockJiraIssue("MOCK-1"), MockJiraIssue("MOCK-2")]


class TestEtlJira(unittest.TestCase):
    """
    Test EtlJira class.
    """

    def test_query(self):
        """
        Test query_bfs()
        """
        etl = EtlJira(MockJiraClass(), MagicMock(), etl_jira_mongo.DEFAULT_PROJECTS,
                      etl_jira_mongo.DEFAULT_BATCH_SIZE)
        result = etl.query_bfs()
        self.assertEqual(result[0].key, "MOCK-1")
        self.assertEqual(len(result), 2)

    def test_save(self):
        """
        Test save_bf_in_mongo()
        """
        expected = [
            OrderedDict([('key', 'MOCK-1'),
                         ('summary', 'This is a fake Jira issue.'),
                         ('_id', 'MOCK-1'),
                         ('project', []),
                         ('first_failing_revision', []),
                         ('fix_revision', [])]),
            OrderedDict([('key', 'MOCK-2'),
                         ('summary', 'This is a fake Jira issue.'),
                         ('_id', 'MOCK-2'),
                         ('project', []),
                         ('first_failing_revision', []),
                         ('fix_revision', [])])
        ]  # yapf: disable

        etl = etl_jira_mongo.EtlJira(MockJiraClass(), MagicMock(), etl_jira_mongo.DEFAULT_PROJECTS,
                                     etl_jira_mongo.DEFAULT_BATCH_SIZE)
        etl._build_failures = MagicMock(name="MongoClient collection", autospec=True)

        issues = etl.query_bfs()
        etl.save_bf_in_mongo(issues)
        etl._build_failures.insert.assert_called_once_with(expected)


# pylint: disable=too-many-lines
class ClickTest(unittest.TestCase):
    """
    Test Cli group command.
    """

    def setUp(self):
        self.runner = CliRunner()


class TestEtlJiraMongoCli(ClickTest):
    """
    Test the etl-jira-mongo CLI interface.
    """

    @patch('signal_processing.etl_jira_mongo.log.setup_logging')
    @patch('signal_processing.etl_jira_mongo.EtlJira')
    @patch('signal_processing.etl_jira_mongo.new_jira_client')
    @patch('signal_processing.etl_jira_mongo.pymongo.MongoClient')
    def _test_cli(self,
                  cli_params,
                  expected_jira_user,
                  expected_jira_password,
                  expected_mongo_uri,
                  expected_projects,
                  expected_batch_size,
                  expected_debug,
                  mock_mongoclient=None,
                  mock_new_jira_client=None,
                  mock_etl_jira=None,
                  mock_setup_logging=None):
        # pylint: disable=too-many-arguments
        mock_mongo = MagicMock()
        mock_mongoclient.return_value = mock_mongo
        mock_jira = MagicMock()
        mock_new_jira_client.return_value = mock_jira, None

        result = self.runner.invoke(main, cli_params)
        self.assertEqual(result.exit_code, 0)
        mock_setup_logging.assert_called_once_with(expected_debug)
        mock_new_jira_client.assert_called_once_with(expected_jira_user, expected_jira_password)
        mock_mongoclient.assert_called_once_with(expected_mongo_uri)
        mock_etl_jira.assert_called_once_with(mock_jira, mock_mongo, expected_projects,
                                              expected_batch_size)

    def test_default_options(self):
        """Test script usage without options."""
        self._test_cli([],
                       None,  # expected_jira_user
                       None,  # expected_jira_password
                       etl_jira_mongo.DEFAULT_MONGO_URI,
                       etl_jira_mongo.DEFAULT_PROJECTS,
                       etl_jira_mongo.DEFAULT_BATCH_SIZE,
                       False)  # yapf: disable

    def test_cronjob_usage(self):
        """Test usage of script defined in cronjobs.yml."""
        jira_user = 'some jira user'
        jira_password = 'some jira password'
        mongo_uri = 'mongodb+srv://rest_of_uri'
        cli_args = ['-u', jira_user, '-p', jira_password, '--mongo-uri', mongo_uri]

        self._test_cli(cli_args,
                       jira_user,
                       jira_password,
                       mongo_uri,
                       etl_jira_mongo.DEFAULT_PROJECTS,
                       etl_jira_mongo.DEFAULT_BATCH_SIZE,
                       False)  # yapf: disable

    def test_one_project_option(self):
        """Test script usage with one --project option."""
        project = "project id"
        cli_args = ['--project', project]

        self._test_cli(cli_args,
                       None,  # expected_jira_user
                       None,  # expected_jira_password
                       etl_jira_mongo.DEFAULT_MONGO_URI,
                       (project, ),
                       etl_jira_mongo.DEFAULT_BATCH_SIZE,
                       False)  # yapf: disable

    def test_multiple_project_option(self):
        """Test script usage with multiple --project options."""
        project1 = "project 1"
        project2 = "project 2"
        cli_args = ['--project', project1, '--project', project2]

        self._test_cli(cli_args,
                       None,  # expected_jira_user
                       None,  # expected_jira_password
                       etl_jira_mongo.DEFAULT_MONGO_URI,
                       (project1, project2),
                       etl_jira_mongo.DEFAULT_BATCH_SIZE,
                       False)  # yapf: disable

    def test_batch_option(self):
        """Test script usage with --batch option."""
        batch_size = 456
        cli_args = ['--batch', batch_size]

        self._test_cli(cli_args,
                       None,  # expected_jira_user
                       None,  # expected_jira_password
                       etl_jira_mongo.DEFAULT_MONGO_URI,
                       etl_jira_mongo.DEFAULT_PROJECTS,
                       batch_size,
                       False)  # yapf: disable

    def test_debug_flag(self):
        """Test script usage with --debug flag."""
        cli_args = ['--debug']

        self._test_cli(cli_args,
                       None,  # expected_jira_user
                       None,  # expected_jira_password
                       etl_jira_mongo.DEFAULT_MONGO_URI,
                       etl_jira_mongo.DEFAULT_PROJECTS,
                       etl_jira_mongo.DEFAULT_BATCH_SIZE,
                       True)  # yapf: disable
