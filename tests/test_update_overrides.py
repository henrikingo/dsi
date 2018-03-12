"""Unit tests for the update_overrides script. Run using nosetests."""

import json
import os
import shutil
import unittest

# TODO: once all shell script tests are moved to python unittests, analysis can be
# made into its own module. This will allow these tests to use absolute imports
# (i.e. import analysis.update_overrides)
import update_overrides
from tests import test_utils
from tests.test_requests_parent import TestRequestsParent


class TestUpdateOverrides(TestRequestsParent):
    """Test class evaluates correctness of the update_overrides script.
    """

    def setUp(self):
        """Specifies the path to output the JSON files. Additionally,
        sets up the common parameters for each operation being tested.
        """
        # the original update_overrides test script does a reference update
        # and then a threshold update before comparing the final output file
        # against the expected result.
        self.intermed_file = test_utils.fixture_file_path('update_override_intermed.json')
        self.output_file = test_utils.fixture_file_path('update_override_test.json')
        self.config_file = test_utils.repo_root_file_path('config.yml')
        self.override_file = test_utils.fixture_file_path('perf_override.json')
        self.regenerate_output_files = False  #Note: causes all tests to pass
        TestRequestsParent.setUp(self)

    def _update_overrides_compare(self, git_hash):
        """General comparison function used for hash-related test cases"""
        reference_args = [
            git_hash, '-c', self.config_file, '-p', 'performance', '-k', 'query', '-f',
            self.override_file, '-d', self.intermed_file, '--verbose', '-t',
            'Queries.FindProjectionDottedField$|Queries.FindProjectionThreeFields$', '-i', 'noise'
        ]

        update_overrides.main(reference_args)

        threshold_args = [
            git_hash, '-c', self.config_file, '-p', 'performance', '-k', 'query', '-f',
            self.intermed_file, '-d', self.output_file, '--verbose', '-t',
            'Queries.FindProjectionDottedField$|Queries.FindProjectionThreeFields$', '--threshold',
            '0.66', '--thread-threshold', '0.77', '-i', 'test_threshold'
        ]
        update_overrides.main(threshold_args)

        os.remove(self.intermed_file)

        expected_json = test_utils.fixture_file_path('update_overrides.json.ok')

        if self.regenerate_output_files:
            shutil.copyfile(self.output_file, expected_json)

        with open(expected_json) as exp_file_handle, open(self.output_file) as obs_file_handle:
            exp_updated_override = json.load(exp_file_handle)
            obs_updated_override = json.load(obs_file_handle)
            self.assertEqual(obs_updated_override, exp_updated_override)

    def test_update_hash_min_prefix(self):
        """Testing update_overrides with the minimum required len 7-character hash prefix.
        """
        git_hash = 'c2af7aba'
        self._update_overrides_compare(git_hash)

    def test_update_hash_mid_prefix(self):
        """Testing update_overrides with a 14-character hash prefix.
        """
        git_hash = 'c2af7abae8d09d'
        self._update_overrides_compare(git_hash)

    def test_update_hash_full(self):
        """Testing update_overrides with the full hash prefix.
        """
        git_hash = 'c2af7abae8d09d290d7457ab77f5a7529806b75a'
        self._update_overrides_compare(git_hash)

    def test_no_ticket_reference_update(self):
        """Testing update_overrides with no ticket parameter & rule reference.
        Test override values are still found and updated.
        """
        git_hash = 'c2af7aba'
        reference_args = [
            git_hash, '-c', self.config_file, '-p', 'performance', '-v', 'linux-*-standalone', '-k',
            'query', '-f', self.override_file, '-d', self.output_file, '--verbose', '-t',
            'Queries.FindProjectionDottedField$|Queries.FindProjectionThreeFields$'
        ]
        update_overrides.main(reference_args)

        expected_json = test_utils.fixture_file_path('update_ref_no_ticket.json.ok')

        if self.regenerate_output_files:
            shutil.copyfile(self.output_file, expected_json)

        with open(expected_json) as exp_file_handle, open(self.output_file) as obs_file_handle:
            exp_updated_override = json.load(exp_file_handle)
            obs_updated_override = json.load(obs_file_handle)
            self.assertEqual(obs_updated_override, exp_updated_override)

    def test_no_ticket_threshold_update(self):
        """Testing update_overrides with no ticket parameter & rule threshold.
        Test override values are still found and updated.
        """
        git_hash = 'c2af7aba'
        override_file = test_utils.fixture_file_path('update_override_reference.json.ok')
        threshold_args = [
            git_hash, '-c', self.config_file, '-p', 'performance', '-k', 'query', '-f',
            override_file, '-d', self.output_file, '--verbose', '-t',
            'Queries.FindProjectionDottedField$|Queries.FindProjectionThreeFields$', '--threshold',
            '0.66', '--thread-threshold', '0.77', '-v', 'linux-*-standalone'
        ]
        update_overrides.main(threshold_args)

        expected_json = test_utils.fixture_file_path('update_thresh_no_ticket.json.ok')
        with open(expected_json) as exp_file_handle, open(self.output_file) as obs_file_handle:
            exp_updated_override = json.load(exp_file_handle)
            obs_updated_override = json.load(obs_file_handle)
            self.assertEqual(obs_updated_override, exp_updated_override)

    def test_no_ticket_no_update(self):
        """Testing update_overrides with no ticket parameter and no relevant overrides found.
        Output file should be identical to the input file.
        """
        git_hash = 'c2af7aba'
        reference_args = [
            git_hash, '-c', self.config_file, '-p', 'performance', '-k', 'misc', '-f',
            self.override_file, '-d', self.output_file, '--verbose', '-t',
            'Queries.FindProjectionDottedField$|Queries.FindProjectionThreeFields$'
        ]
        update_overrides.main(reference_args)

        expected_json = self.override_file
        with open(expected_json) as exp_file_handle, open(self.output_file) as obs_file_handle:
            exp_updated_override = json.load(exp_file_handle)
            obs_updated_override = json.load(obs_file_handle)
            self.assertEqual(obs_updated_override, exp_updated_override)

    def tearDown(self):
        """Deletes output JSON files after each test case"""
        os.remove(self.output_file)
        TestRequestsParent.tearDown(self)


if __name__ == '__main__':
    unittest.main()
