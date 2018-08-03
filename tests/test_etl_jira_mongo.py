"""
Unit tests for signal_processing/etl_jira_mongo.py.
"""

import copy
from collections import OrderedDict
import unittest
from mock import MagicMock

from signal_processing import etl_jira_mongo


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


OPTIONS = {
    "jira_user": "mock_jira_user",
    "jira_password": "mock_jira_password",
    "mongo_uri": "mongodb+srv://user:pass@example.com/perf?retryWrites=true",
    # Defaults:
    "projects": etl_jira_mongo.PROJECTS,
    "batch": etl_jira_mongo.BATCH_SIZE,
    "debug": False
}


class TestEtlJira(unittest.TestCase):
    """
    Test etl_jira_mongo.EtlJira class.
    """

    def setUp(self):
        self.options = copy.deepcopy(OPTIONS)

    def test_query(self):
        """
        Test query_bfs()
        """
        etl = etl_jira_mongo.EtlJira(self.options)
        etl._jira = MockJiraClass()
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
        ]  #  yapf: disable

        etl = etl_jira_mongo.EtlJira(self.options)
        etl._jira = MockJiraClass()
        etl._coll = MagicMock(name="MongoClient collection", autospec=True)

        issues = etl.query_bfs()
        etl.save_bf_in_mongo(issues)
        etl._coll.insert.assert_called_once_with(expected)
