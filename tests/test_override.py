"""Unit tests for the Override class. Run using nosetests."""

import unittest
from mock import patch

from tests import test_utils
import util
from evergreen.override import Override, TestDataNotFound # pylint: disable=import-error


class TestOverride(unittest.TestCase):
    """Test class evaluates correctness of operations to override rule JSON files.
    """

    def setUp(self):
        """Specifies the paths used to fetch JSON testing files. Additionally,
        sets up the common parameters for each operation being tested.
        """
        # parameters used in test cases
        self.project = 'performance'
        self.git_hash = 'c2af7ab'
        self.config_file = test_utils.repo_root_file_path('config.yml')
        self.verbose = True

    def test_update_reference(self):
        """Test Override.update_override with rule reference
        """
        variants = '.*'
        tasks = 'query'
        tests_to_update = 'Queries.FindProjectionDottedField$|Queries.FindProjectionThreeFields$'
        override_file = test_utils.fixture_file_path('perf_override.json')
        original_override_info = util.get_json(override_file)
        ticket = 'PERF-REF'
        update_obj = Override(self.project,
                              override_info=override_file,
                              config_file=self.config_file,
                              reference=self.git_hash,
                              variants=variants.split('|'),
                              tasks=tasks.split('|'),
                              tests=tests_to_update.split('|'),
                              verbose=self.verbose)

        update_obj.update_override('reference', ticket=ticket)

        updated_override = test_utils.read_fixture_json_file('update_override_exp.json.ok')

        self.assertEqual(update_obj.overrides, updated_override)

        # Quick check of the update_override_reference wrapper function.
        # First, reset the override file information.
        update_obj.overrides = original_override_info
        update_obj.update_override_reference(ticket=ticket)
        self.assertEqual(update_obj.overrides, updated_override)

    def test_update_threshold(self):
        """Test Override.update_override with rule threshold
        """
        variants = '.*'
        tasks = 'query'
        tests_to_update = 'Queries.FindProjectionDottedField$|Queries.FindProjectionThreeFields$'
        threshold = 0.66
        thread_threshold = 0.77
        override_file = test_utils.fixture_file_path('update_override_exp.json.ok')
        original_override_info = util.get_json(override_file)
        ticket = 'PERF-THRESH'

        update_obj = Override(self.project,
                              override_info=override_file,
                              config_file=self.config_file,
                              reference=self.git_hash,
                              variants=variants.split('|'),
                              tasks=tasks.split('|'),
                              tests=tests_to_update.split('|'),
                              verbose=self.verbose)

        new_override_val = {'threshold': threshold, 'thread_threshold': thread_threshold}
        update_obj.update_override('threshold',
                                   new_override_val=new_override_val,
                                   ticket=ticket)

        updated_override = test_utils.read_fixture_json_file(
            'update_override_threshold_exp.json.ok')
        self.assertEqual(update_obj.overrides, updated_override)

        # Quick check of the update_override_threshold wrapper function.
        # First, reset the override file information.
        update_obj.overrides = original_override_info
        update_obj.update_override_threshold(threshold, thread_threshold, ticket=ticket)
        self.assertEqual(update_obj.overrides, updated_override)

    def test_delete_and_update(self):
        """Test Override.delete_overrides_by_ticket
        """
        override_file = test_utils.fixture_file_path('perf_delete.json')
        rules = ['reference', 'ndays', 'threshold']
        ticket = 'PERF-002'

        update_obj = Override(self.project,
                              override_info=override_file,
                              config_file=self.config_file,
                              reference=self.git_hash,
                              verbose=self.verbose)
        update_obj.delete_overrides_by_ticket(ticket, rules)

        expected_overrides = test_utils.read_fixture_json_file('delete_update_override.json.ok')
        self.assertEqual(update_obj.overrides, expected_overrides)

    @patch('evergreen.evergreen_client.Client.get_recent_revisions')
    def test_delete_latest_update(self, mock_get_revisions):
        """Test Override.delete_overrides_by_ticket with no revision specified.
        """
        mock_get_revisions.return_value = test_utils.read_fixture_json_file(
            'performance_latest_revisions.json')
        override_file = test_utils.fixture_file_path('perf_delete.json')
        rules = ['reference', 'ndays', 'threshold']
        ticket = 'PERF-002'

        update_obj = Override(self.project,
                              override_info=override_file,
                              config_file=self.config_file,
                              verbose=self.verbose)
        update_obj.delete_overrides_by_ticket(ticket, rules)

        expected_overrides = test_utils.read_fixture_json_file('delete_update_latest.json.ok')
        self.assertEqual(update_obj.overrides, expected_overrides)

    def test_delete_latest_not_found(self):
        """Test Override.delete_overrides_by_ticket unable to find a recent revision with
        data for all tests that need to be updated.
        The override file passed in contains a test "Commands.UniqueTestCase" that should
        not be present in any project revision, so no mocking is needed here.
        """
        override_file = test_utils.fixture_file_path('perf_delete_unique_test.json')
        rules = ['reference', 'ndays', 'threshold']
        ticket = 'PERF-002'

        update_obj = Override(self.project,
                              override_info=override_file,
                              config_file=self.config_file,
                              verbose=self.verbose)

        with self.assertRaises(TestDataNotFound):
            update_obj.delete_overrides_by_ticket(ticket, rules)

    def test_get_tickets_rule_reference(self):
        """Test Override.get_tickets for rule reference on perf_override.json
        """
        override_file = test_utils.read_fixture_json_file('perf_override.json')
        override_obj = Override(self.project, override_info=override_file)
        expected_ref_tickets = set([u'BF-1262', u'BF-1449', u'BF-1461', u'SERVER-19901',
                                    u'SERVER-20623', u'SERVER-21263', u'BF-1169', u'SERVER-20018',
                                    u'mmapspedup', u'geo', u'SERVER-21080'])
        self.assertEqual(override_obj.get_tickets(), expected_ref_tickets)

    def test_get_tickets_rule_threshold(self):
        """Test Override.get_tickets for rule threshold on perf_override.json
        """
        override_file = test_utils.fixture_file_path('perf_override.json')
        override_obj = Override(self.project, override_info=override_file)
        expected_thresh_tickets = set([u'PERF-443'])
        self.assertEqual(override_obj.get_tickets(rule='threshold'), expected_thresh_tickets)

    def test_get_tickets_none(self):
        """Test Override.get_tickets returns empty set when override file is None
        """
        override_obj = Override(self.project, override_info=None)
        self.assertEqual(override_obj.get_tickets(), set([]))

    def test_get_overrides_by_ticket(self):
        """Test Override.get_overrides_by_ticket
        """

        test1 = {"ticket": ["1", "2"]}
        test2 = {"ticket": ["1", "3"]}
        test3 = {"ticket": ["2", "3"]}
        override_dict = {
            "variant1": {
                "ndays": {
                    "test1": test1
                },
                "reference": {
                    "test2": test2
                }
            },
            "variant2": {
                "ndays": {
                    "test3": test3
                }
            }
        }
        override = Override("", override_dict)
        expected_results = sorted([
            ("variant1", "ndays", "test1", test1),
            ("variant1", "reference", "test2", test2)])
        self.assertEqual(sorted(override.get_overrides_by_ticket("1")), expected_results)
        expected_results = sorted([
            ("variant1", "ndays", "test1", test1),
            ("variant2", "ndays", "test3", test3)])
        self.assertEqual(sorted(override.get_overrides_by_ticket("2")), expected_results)

    def test_rename_ticket(self):
        """Test Override.rename_ticket correctly renames tickets in place.
        """

        test1_tickets = ["1", "2", "bar"]
        test2_tickets = ["4", "2", "baz"]
        override_dict = {
            "variant1": {
                "ndays": {
                    "test1": {"ticket": test1_tickets}
                }
            },
            "variant2": {
                "reference": {
                    "test2": {"ticket": test2_tickets}
                }
            }
        }
        override = Override("", override_dict)
        override.rename_ticket("2", "foo")
        self.assertEqual(test1_tickets, ["1", "foo", "bar"])
        self.assertEqual(test2_tickets, ["4", "foo", "baz"])

if __name__ == '__main__':
    unittest.main()
