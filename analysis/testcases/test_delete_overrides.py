"""Unit tests for the delete_overrides script. Run using nosetests."""

import json
import os
import sys
import unittest

# TODO: once all shell script tests are moved to python unittests, analysis can be
# made into its own module. This will allow these tests to use absolute imports
# (i.e. import analysis.update_overrides)
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import delete_overrides  # pylint: disable=import-error,wrong-import-position


class TestDeleteOverrides(unittest.TestCase):
    """Test class evaluates correctness of the delete_overrides script.
    """

    def setUp(self):
        """Specifies the paths to output the JSON files. Additionally,
        sets up the common parameters for each operation being tested.
        """
        self.abs_path = os.path.dirname(os.path.abspath(__file__))
        self.unittest_files = os.path.join(self.abs_path, 'unittest-files')
        self.reference_files = os.path.join(self.abs_path, 'reference')
        self.output_file = os.path.join(self.unittest_files,
                                        'delete_override_test.json')
        self.config_file = os.path.join(self.abs_path, 'config.yml')

    def _path_to_reference(self, prefix, rule, ticket):
        # reference file naming convention
        name = '.'.join([prefix, rule, ticket, 'json.ok'])
        return os.path.join(self.reference_files, name)

    def _delete_overrides_compare(self, override_file, ticket, rule, expected_json):
        """General comparison function used for all the test cases"""
        args = [ticket, '-f', override_file, '-d', self.output_file, '-r', rule,
                '-c', self.config_file, '--verbose']
        delete_overrides.main(args)

        with open(expected_json) as exp_file_handle, open(self.output_file) as obs_file_handle:
            exp_updated_override = json.load(exp_file_handle)
            obs_updated_override = json.load(obs_file_handle)
            self.assertEqual(obs_updated_override, exp_updated_override)

    def test_perf_none_deleted(self):
        """Test deletion where ticket 'PERF-443' does not appear under rule reference.
        """
        override_file = os.path.join(self.abs_path, 'perf_override.json')
        ticket = 'PERF-443'
        rule = 'reference'
        compare_against = self._path_to_reference('delete.perf', rule, ticket)
        self._delete_overrides_compare(override_file, ticket, rule, compare_against)

    def test_perf_threshold_deleted(self):
        """Test deletion where ticket 'PERF-443' appears under rule threshold.
        """
        override_file = os.path.join(self.abs_path, 'perf_override.json')
        ticket = 'PERF-443'
        rule = 'threshold'
        compare_against = self._path_to_reference('delete.perf', rule, ticket)
        self._delete_overrides_compare(override_file, ticket, rule, compare_against)

    def test_perf_all_deleted(self):
        """Test deletion for ticket 'noise' in all rules. 'noise' is the only
        ticket associated with each test override, so a clean deletion without
        updates can be made.
        """
        override_file = os.path.join(self.abs_path, 'perf_override.json')
        ticket = 'noise'
        rule = 'all'
        compare_against = self._path_to_reference('delete.perf', rule, ticket)
        self._delete_overrides_compare(override_file, ticket, rule, compare_against)

    def test_sysperf_none_deleted(self):
        """Test deletion where ticket 'PERF-335' does not appear under rule reference.
        """
        override_file = os.path.join(self.abs_path, 'system_perf_override.json')
        ticket = 'PERF-335'
        rule = 'reference'
        compare_against = self._path_to_reference('delete.system_perf', rule, ticket)
        self._delete_overrides_compare(override_file, ticket, rule, compare_against)

    def test_sysperf_threshold_deleted(self):
        """Test deletion where ticket 'PERF-335' appears under rule threshold.
        """
        override_file = os.path.join(self.abs_path, 'system_perf_override.json')
        ticket = 'PERF-335'
        rule = 'threshold'
        compare_against = self._path_to_reference('delete.system_perf', rule, ticket)
        self._delete_overrides_compare(override_file, ticket, rule, compare_against)

    def test_sysperf_all_deleted(self):
        """Test deletion for ticket 'noise' in all rules. 'BF-1418' is the only
        ticket associated with each test override, so a clean deletion without
        updates can be made.
        """
        override_file = os.path.join(self.abs_path, 'system_perf_override.json')
        ticket = 'BF-1418'
        rule = 'all'
        compare_against = self._path_to_reference('delete.system_perf', rule, ticket)
        self._delete_overrides_compare(override_file, ticket, rule, compare_against)

    def test_delete_and_update(self):
        """Test deletion for ticket 'PERF-REMOVE' in all rules, where some test
        overrides cannot be deleted (other tickets associated with them)--update
        based on the given reference commit.
        """
        override_file = os.path.join(self.abs_path, 'perf_delete.json')
        use_reference = 'c2af7ab'
        ticket = 'PERF-002'
        rule = 'all'
        args = [ticket, '-n', use_reference, '-f', override_file, '-d', self.output_file,
                '-r', rule, '-c', self.config_file, '--verbose']
        delete_overrides.main(args)

        expected_json = os.path.join(self.unittest_files, 'delete_update_override.json.ok')
        with open(expected_json) as exp_file_handle, open(self.output_file) as obs_file_handle:
            exp_updated_override = json.load(exp_file_handle)
            obs_updated_override = json.load(obs_file_handle)
            self.assertEqual(obs_updated_override, exp_updated_override)

    def tearDown(self):
        """Deletes output JSON file after each test case"""
        os.remove(self.output_file)

if __name__ == '__main__':
    unittest.main()
