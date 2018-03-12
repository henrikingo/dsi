"""Unit tests for the delete_overrides script. Run using nosetests."""
import logging
import json
import os
import shutil
import unittest
from testfixtures import LogCapture

import delete_overrides
from tests import test_utils
from tests.test_requests_parent import TestRequestsParent


class TestDeleteOverrides(TestRequestsParent):
    """Test class evaluates correctness of the delete_overrides script.
    """

    def setUp(self):
        """Specifies the paths to output the JSON files. Additionally,
        sets up the common parameters for each operation being tested.
        """
        self.output_file = test_utils.fixture_file_path('delete_override_test.json')
        self.config_file = test_utils.repo_root_file_path('config.yml')
        self.regenerate_output_files = False  #Note: causes all tests that compare a file to pass
        TestRequestsParent.setUp(self)

    @staticmethod
    def _path_to_reference(prefix, rule, ticket):
        # reference file naming convention
        name = '.'.join([prefix, rule, ticket, 'json.ok'])
        return test_utils.fixture_file_path(name)

    def _delete_overrides_compare(self, override_file, ticket, rule, expected_json):
        """General comparison function used for all the test cases"""
        use_reference = 'c2af7aba'
        args = [
            ticket, '-n', use_reference, '-f', override_file, '-d', self.output_file, '-r', rule,
            '-c', self.config_file, '--verbose'
        ]
        delete_overrides.main(args)
        if self.regenerate_output_files:
            shutil.copyfile(self.output_file, expected_json)
        with open(expected_json) as exp_file_handle, open(self.output_file) as obs_file_handle:
            exp_updated_override = json.load(exp_file_handle)
            obs_updated_override = json.load(obs_file_handle)
            self.assertEqual(obs_updated_override, exp_updated_override)

    def test_perf_none_deleted(self):
        """Test deletion where ticket 'PERF-443' does not appear under rule reference.
        """
        override_file = test_utils.fixture_file_path('perf_override.json')
        ticket = 'PERF-443'
        rule = 'reference'
        compare_against = self._path_to_reference('delete.perf', rule, ticket)
        with LogCapture(level=logging.CRITICAL) as crit:
            self._delete_overrides_compare(override_file, ticket, rule, compare_against)
            crit_logs = set(crit.actual())
            crit_expected = set([('override.update.warnings', 'CRITICAL',
                                  'No overrides have changed.')])
            self.assertEqual(crit_expected, crit_logs)

    def test_perf_threshold_deleted(self):
        """Test deletion where ticket 'PERF-443' appears under rule threshold.
        """
        override_file = test_utils.fixture_file_path('perf_override.json')
        ticket = 'PERF-443'
        rule = 'threshold'
        compare_against = self._path_to_reference('delete.perf', rule, ticket)
        with LogCapture(level=logging.CRITICAL) as crit:
            self._delete_overrides_compare(override_file, ticket, rule, compare_against)
            crit_logs = set(crit.actual())
            crit_expected = set()
            self.assertEqual(crit_expected, crit_logs)

        with LogCapture(level=logging.INFO) as info:
            self._delete_overrides_compare(override_file, ticket, rule, compare_against)
            info_logs = set(info.actual())
            info_expected = set([('override.update.information', 'INFO',
                                  'The following tests were deleted:'),
                                 ('override.update.information', 'INFO',
                                  '{\n  "linux-wt-standalone": {\n    "query": [\n      '
                                  '"Queries.UniqueIdx.MultipleUniqueIndices"\n    ]\n  }\n}')])
            self.assertTrue(info_expected.issubset(info_logs))

    def test_perf_all_deleted(self):
        """Test deletion for ticket 'PERF-755' in all rules. 'PERF-755' is the only
        ticket associated with each test override, so a clean deletion without
        updates can be made.
        """
        override_file = test_utils.fixture_file_path('perf_override.json')
        ticket = 'PERF-755'
        rule = 'all'
        compare_against = self._path_to_reference('delete.perf', rule, ticket)
        with LogCapture(level=logging.CRITICAL) as crit:
            self._delete_overrides_compare(override_file, ticket, rule, compare_against)
            crit_logs = set(crit.actual())
            crit_expected = set()
            self.assertEqual(crit_expected, crit_logs)
        with LogCapture(level=logging.INFO) as info:
            self._delete_overrides_compare(override_file, ticket, rule, compare_against)
            info_logs = set(info.actual())
            expected_logs = set([('override.update.information', 'INFO',
                                  'The following tests were deleted:'),
                                 ('override.update.information', 'INFO', '{\n  '
                                  '"linux-mmap-repl-compare": {\n    "misc": [\n      '
                                  '"Commands.DistinctWithoutIndex"\n    ]\n  },\n  '
                                  '"linux-mmap-standalone": {\n    "geo": [\n      '
                                  '"Geo.near.2d.withFilter.find30"\n    ],\n    "query": [\n      '
                                  '"Queries.FindProjectionThreeFields"\n    ]\n  },\n  '
                                  '"linux-wt-mmap-repl-compare": {\n    "misc": [\n      '
                                  '"Commands.DistinctWithoutIndex"\n    ]\n  },\n  '
                                  '"linux-wt-mmap-standalone-compare": {\n    "misc": [\n      '
                                  '"Commands.DistinctWithoutIndex"\n    ]\n  },\n  '
                                  '"linux-wt-repl": {\n    "misc": [\n      '
                                  '"Commands.DistinctWithoutIndex"\n    ]\n  },\n  '
                                  '"linux-wt-repl-compare": {\n    "misc": [\n      '
                                  '"Commands.DistinctWithoutIndex"\n    ]\n  },\n  '
                                  '"linux-wt-standalone": {\n    "geo": [\n      '
                                  '"Geo.near.2d.findOne"\n    ],\n    "misc": [\n      '
                                  '"Commands.DistinctWithoutIndex"\n    ],\n    "query": [\n      '
                                  '"Queries.FindProjectionThreeFields"\n    ]\n  }\n}')])
            self.assertTrue(expected_logs.issubset(info_logs))

    def test_sysperf_none_deleted(self):
        """Test deletion where ticket 'PERF-335' does not appear under rule reference.
        """
        override_file = test_utils.fixture_file_path('system_perf_override.json')
        ticket = 'PERF-335'
        rule = 'reference'
        compare_against = self._path_to_reference('delete.system_perf', rule, ticket)
        with LogCapture(level=logging.CRITICAL) as crit:
            self._delete_overrides_compare(override_file, ticket, rule, compare_against)
            crit_logs = set(crit.actual())
            crit_expected = set([('override.update.warnings', 'CRITICAL',
                                  'No overrides have changed.')])
            self.assertEqual(crit_expected, crit_logs)

    def test_sysperf_threshold_deleted(self):
        """Test deletion where ticket 'PERF-335' appears under rule threshold.
        """
        override_file = test_utils.fixture_file_path('system_perf_override.json')
        ticket = 'PERF-335'
        rule = 'threshold'
        compare_against = self._path_to_reference('delete.system_perf', rule, ticket)
        with LogCapture(level=logging.CRITICAL) as crit:
            self._delete_overrides_compare(override_file, ticket, rule, compare_against)
            crit_logs = set(crit.actual())
            crit_expected = set()
            self.assertEqual(crit_logs, crit_expected)
        with LogCapture(level=logging.INFO) as info:
            self._delete_overrides_compare(override_file, ticket, rule, compare_against)
            info_logs = set(info.actual())
            info_expected = set([('override.update.information', 'INFO',
                                  'The following tests were deleted:'),
                                 ('override.update.information', 'INFO',
                                  '{\n  "linux-1-node-replSet": {\n    "core_workloads_WT": [\n'
                                  '      "removemulti_jtrue-wiredTiger"\n    ]\n  },\n  '
                                  '"linux-3-node-replSet": {\n    "core_workloads_WT": [\n      '
                                  '"removemulti_jtrue-wiredTiger"\n    ],\n    '
                                  '"industry_benchmarks_WT": [\n      '
                                  '"ycsb_50read50update_w_majority-wiredTiger"\n    ]\n  },\n  '
                                  '"linux-3-shard": {\n    "core_workloads_WT": [\n      '
                                  '"moveChunk_secondaryThrottle_true_waitForDelete_false-'
                                  'wiredTiger"\n    ],\n    "industry_benchmarks_WT": [\n      '
                                  '"ycsb_50read50update_w_majority-wiredTiger"\n    ]\n  },\n  '
                                  '"linux-standalone": {\n    "core_workloads_WT": [\n      '
                                  '"removemulti_jtrue-wiredTiger"\n    ]\n  }\n}')])
            self.assertTrue(info_expected.issubset(info_logs))

    def test_sysperf_all_deleted(self):
        """Test deletion for ticket 'BF-1418' in all rules. 'BF-1418' is the only
        ticket associated with each test override, so a clean deletion without
        updates can be made.
        """
        override_file = test_utils.fixture_file_path('system_perf_override.json')
        ticket = 'BF-1418'
        rule = 'all'
        compare_against = self._path_to_reference('delete.system_perf', rule, ticket)
        with LogCapture(level=logging.CRITICAL) as crit:
            self._delete_overrides_compare(override_file, ticket, rule, compare_against)
            crit_logs = set(crit.actual())
            crit_expected = set()
            self.assertEqual(crit_logs, crit_expected)
        with LogCapture(level=logging.INFO) as info:
            self._delete_overrides_compare(override_file, ticket, rule, compare_against)
            info_logs = set(info.actual())
            info_expected = set([('override.update.information', 'INFO',
                                  'The following tests were deleted:'),
                                 ('override.update.information', 'INFO', '{\n  '
                                  '"linux-1-node-replSet": {\n    "industry_benchmarks_MMAPv1": [\n'
                                  '      "ycsb_50read50update-mmapv1"\n    ]\n  },\n  '
                                  '"linux-3-node-replSet": {\n    "industry_benchmarks_MMAPv1": [\n'
                                  '      "ycsb_50read50update-mmapv1"\n    ]\n  },\n  '
                                  '"linux-3-shard": {\n    "industry_benchmarks_MMAPv1": [\n      '
                                  '"ycsb_50read50update-mmapv1"\n    ]\n  },\n  "linux-standalone":'
                                  ' {\n    "industry_benchmarks_MMAPv1": [\n      '
                                  '"ycsb_50read50update-mmapv1"\n    ]\n  }\n}')])
            self.assertTrue(info_expected.issubset(info_logs))

    def test_delete_and_update(self):
        """Test deletion for ticket 'PERF-002' in all rules, where some test
        overrides cannot be deleted (other tickets associated with them)--update
        based on the given reference commit.
        """
        override_file = test_utils.fixture_file_path('perf_delete.json')
        ticket = 'PERF-002'
        rule = 'all'
        compare_against = test_utils.fixture_file_path('delete_update_override.json.ok')
        with LogCapture(level=logging.CRITICAL) as crit:
            self._delete_overrides_compare(override_file, ticket, rule, compare_against)
            crit_logs = set(crit.actual())
            crit_expected = set()
            self.assertEqual(crit_logs, crit_expected)
        with LogCapture(level=logging.INFO) as info:
            self._delete_overrides_compare(override_file, ticket, rule, compare_against)
            info_logs = set(info.actual())
            info_expected = set([('override.update.information', 'INFO',
                                  'The following tests were deleted:'),
                                 ('override.update.information', 'INFO',
                                  '{\n  "linux-mmap-standalone": {\n    "query": [\n      '
                                  '"Queries.FindProjectionThreeFields"\n    ]\n  },\n  '
                                  '"linux-wt-standalone": {\n    "misc": [\n      '
                                  '"Commands.CountsIntIDRange"\n    ]\n  }\n}'),
                                 ('override.update.information', 'INFO', 'The following tests were '
                                  'overridden for rule reference:'),
                                 ('override.update.information', 'INFO', '{\n  "linux-mmap-repl": '
                                  '{\n    "insert": [],\n    "misc": [\n      '
                                  '"Commands.CountsIntIDRange"\n    ],\n    "singleThreaded": [],\n'
                                  '    "update": []\n  },\n  "linux-mmap-standalone": {\n    '
                                  '"geo": [\n      "Geo.near.2d.findOne"\n    ],\n    '
                                  '"insert": [],\n    "misc": [],\n    "query": [],\n    '
                                  '"singleThreaded": [],\n    "update": [],\n    "where": []\n  '
                                  '}\n}'), ('override.update.information', 'INFO',
                                            'The following tests were overridden for rule ndays:'),
                                 ('override.update.information', 'INFO', '{\n  '
                                  '"linux-mmap-standalone": {\n    "geo": [],\n    '
                                  '"insert": [],\n    "misc": [],\n    "query": [\n      '
                                  '"Queries.FindProjection"\n    ],\n    "singleThreaded": [],\n'
                                  '    "update": [],\n    "where": []\n  }\n}')])
            self.assertTrue(info_expected.issubset(info_logs))

    def tearDown(self):
        """Deletes output JSON file after each test case"""
        os.remove(self.output_file)
        TestRequestsParent.tearDown(self)


if __name__ == '__main__':
    unittest.main()
