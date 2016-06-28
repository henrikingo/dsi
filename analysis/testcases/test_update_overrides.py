"""Unit tests for the update_overrides script. Run using nosetests."""

import json
import os
import sys
import unittest

# TODO: once all shell script tests are moved to python unittests, analysis can be
# made into its own module. This will allow these tests to use absolute imports
# (i.e. import analysis.update_overrides)
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import update_overrides  # pylint: disable=import-error,wrong-import-position


class TestUpdateOverrides(unittest.TestCase):
    """Test class evaluates correctness of the update_overrides script.
    """

    def setUp(self):
        """Specifies the path to output the JSON files. Additionally,
        sets up the common parameters for each operation being tested.
        """
        self.abs_path = os.path.dirname(os.path.abspath(__file__))
        self.unittest_files = os.path.join(self.abs_path, 'unittest-files')
        self.reference_files = os.path.join(self.abs_path, 'reference')

        # the original update_overrides test script does a reference update
        # and then a threshold update before comparing the final output file
        # against the expected result.
        self.intermed_file = os.path.join(self.unittest_files,
                                          'update_override_intermed.json')
        self.output_file = os.path.join(self.unittest_files,
                                        'update_override_test.json')
        self.config_file = os.path.join(self.abs_path, 'config.yml')
        self.override_file = os.path.join(self.abs_path, 'perf_override.json')

    def _update_overrides_compare(self, git_hash):
        """General comparison function used for all the test cases"""
        reference_args = [git_hash, '-c', self.config_file, '-p', 'performance', '-k', 'query',
                          '-f', self.override_file, '-d', self.intermed_file, '--verbose', '-t',
                          'Queries.FindProjectionDottedField$|Queries.FindProjectionThreeFields$',
                          'noise']
        update_overrides.main(reference_args)

        threshold_args = [git_hash, '-c', self.config_file, '-p', 'performance', '-k', 'query',
                          '-f', self.intermed_file, '-d', self.output_file, '--verbose', '-t',
                          'Queries.FindProjectionDottedField$|Queries.FindProjectionThreeFields$',
                          '--threshold', '0.66', '--thread-threshold', '0.77', 'test_threshold']
        update_overrides.main(threshold_args)

        expected_json = os.path.join(self.reference_files, 'update_overrides.json.ok')
        with open(expected_json) as exp_file_handle, open(self.output_file) as obs_file_handle:
            exp_updated_override = json.load(exp_file_handle)
            obs_updated_override = json.load(obs_file_handle)
            self.assertEqual(obs_updated_override, exp_updated_override)

    def test_update_hash_min_prefix(self):
        """Testing update_overrides with the minimum required len 7-character hash prefix.
        """
        git_hash = 'c2af7ab'
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

    def tearDown(self):
        """Deletes output JSON files after each test case"""
        os.remove(self.intermed_file)
        os.remove(self.output_file)

if __name__ == '__main__':
    unittest.main()
