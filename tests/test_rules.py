"""Unit tests for the rules module. Run using nosetests."""

import os
import unittest

from dateutil import parser as date_parser

import readers
import rules
from tests import test_utils
import util


class TestResourceRules(unittest.TestCase):
    """Test class evaluates correctness of resource sanity check rules.
    """

    # pylint: disable=too-many-instance-attributes,too-many-public-methods
    def setUp(self):
        """Specifies the paths used to fetch JSON testing files. Additionally,
        sets up the common parameters for each operation being tested.
        """
        # parameters used in test cases
        self.path_ftdc_3node_repl = test_utils.fixture_file_path(
            'linux_3node_replSet_p1.ftdc.metrics')
        self.single_chunk_3node = self._first_chunk(self.path_ftdc_3node_repl)
        self.times_3node = self.single_chunk_3node[rules.FTDC_KEYS['time']]
        self.members_3node = ['0', '1', '2']

        path_ftdc_standalone = test_utils.fixture_file_path('core_workloads_wt.ftdc.metrics')
        self.single_chunk_standalone = self._first_chunk(path_ftdc_standalone)
        self.times_standalone = self.single_chunk_standalone[rules.FTDC_KEYS['time']]

        self.path_3shard_directory = test_utils.fixture_file_path('test_replset_resource_rules')
        self.path_ftdc_repllag = test_utils.fixture_file_path('test_repllag')

    @staticmethod
    def _first_chunk(ftdc_filepath):
        """Short helper to only use the first chunk of a file
        """
        for chunk in readers.read_ftdc(ftdc_filepath):
            return chunk

    def test_get_cache_max(self):
        """Test that we can get the configured cache size from a chunk
        """
        cache_max_3node = 31122784256
        observed = rules.get_configured_cache_size(self.single_chunk_3node)
        self.assertEqual(observed, cache_max_3node)

    def test_get_oplog_max(self):
        """Test that we can get the configured oplog size from a chunk
        """
        oplog_max_3node = 161061273600
        observed = rules.get_configured_oplog_size(self.single_chunk_3node)
        self.assertEqual(observed, oplog_max_3node)

    def test_get_repl_members(self):
        """Test that we can return a set of members from a 3-node replSet FTDC chunk
        """
        observed = rules.get_repl_members(self.single_chunk_3node)
        expected = ['0', '1', '2']
        self.assertEqual(observed, expected)

    def test_no_repl_members(self):
        """Test that we cannot return a set of members from a standalone FTDC chunk
        """
        observed = rules.get_repl_members(self.single_chunk_standalone)
        expected = []
        self.assertEqual(observed, expected)

    def test_below_cache_max_success(self):
        """Test expected success for case of current cache size below configured cache size
        """
        cache_max_3node = 31122784256
        observed = rules.below_configured_cache_size(self.single_chunk_3node, self.times_3node,
                                                     cache_max_3node)
        expected = {}
        self.assertEqual(observed, expected)

    def test_below_cache_max_fail(self):
        """Test expected failure for case of current cache size being above configured cache size
        """
        configured_cache_size = 100
        observed = rules.below_configured_cache_size(self.single_chunk_3node, self.times_3node,
                                                     configured_cache_size)
        expected = {
            'times': self.times_3node,
            'compared_values': [(32554, ), (32554, )],
            'labels': ('current cache size (bytes)', ),
            'additional': {
                'WT configured cache size (bytes)': configured_cache_size
            }
        }
        self.assertEqual(observed, expected)

    def test_below_oplog_max_success(self):
        """Test expected success for case of current oplog size below configured oplog size
        """
        oplog_max_3node = 161061273600
        observed = rules.below_configured_oplog_size(self.single_chunk_3node, self.times_3node,
                                                     oplog_max_3node)
        expected = {}
        self.assertEqual(observed, expected)

    def test_below_oplog_max_fail(self):
        """Test expected failure for case of current oplog size above configured oplog size
        """
        configured_oplog_size = 10
        observed = rules.below_configured_oplog_size(self.single_chunk_3node, self.times_3node,
                                                     configured_oplog_size)
        expected = {
            'times': self.times_3node,
            'compared_values': [(86, ), (86, )],
            'labels': ('current oplog size (MB)', ),
            'additional': {
                'WT configured max oplog size (MB)': configured_oplog_size,
                'rule': 'current size <= (max size * 1.1)'
            }
        }
        self.assertEqual(observed, expected)

    def test_rule_not_applicable(self):
        """Test case where a rule does not apply to a variant
        """
        configured_oplog_size = 0
        observed = rules.below_configured_oplog_size(self.single_chunk_standalone,
                                                     self.times_standalone, configured_oplog_size)
        expected = {}
        self.assertEqual(observed, expected)

    def test_heap_cache_success(self):
        """Test expected success for cache vs. heap size evaluation
        """
        rules.CACHE_ALLOCATOR_OVERHEAD = 0.08
        observed = rules.compare_heap_cache_sizes(self.single_chunk_standalone,
                                                  self.times_standalone)
        expected = {}
        self.assertEqual(observed, expected)

    def test_heap_cache_fail(self):
        """Test expected failure for cache vs. heap size evaluation
        """
        rules.CACHE_ALLOCATOR_OVERHEAD = -1.0
        observed = rules.compare_heap_cache_sizes(self.single_chunk_3node, self.times_3node)
        expected = {
            'times': self.times_3node,
            'compared_values': [(32554, 61972480), (32554, 64008192)],
            'labels': ('current cache size (bytes)', 'tcmalloc generic heap size (bytes)')
        }
        self.assertEqual(observed, expected)

        # Reset to configured. Would rather this be in a config, iffy on testing this way.
        rules.CACHE_ALLOCATOR_OVERHEAD = 0.08

    def test_max_connections_success(self):
        """Test expected success for current # connections below our specified upper bound
        """
        max_thread_level = 64
        observed = rules.max_connections(self.single_chunk_standalone, self.times_standalone,
                                         max_thread_level, [])
        expected = {}
        self.assertEqual(observed, expected)

    def test_max_connections_fail(self):
        """Test expected failure for current # connections above our specified upper bound
        """
        max_thread_level = -13
        observed = rules.max_connections(self.single_chunk_3node, self.times_3node,
                                         max_thread_level, self.members_3node)
        expected = {
            'times': self.times_3node,
            'compared_values': [(3, ), (3, )],
            'labels': ('number of current connections', ),
            'additional': {
                'max thread level for this task': max_thread_level,
                'connections between members? (4 * N)': 12,
                'connections to MC and shell': 2,
                'fudge_factor': 20,
                'rule': '# connections <= (2 * max thread level + 2 + 12 + 20)'
            }
        }
        self.assertEqual(observed, expected)

    def test_member_state_success(self):
        """Test expected success for members all in 'healthy' states
        """
        observed = rules.repl_member_state(self.single_chunk_3node, self.times_3node,
                                           self.members_3node, None)  # no test times
        expected = {}
        print observed
        self.assertEqual(observed, expected)

    def test_member_state_fail(self):
        """Test expected failure for member discovered in an 'unhealthy' state
        """
        rules.FLAG_MEMBER_STATES[2] = 'SECONDARY'
        observed = rules.repl_member_state(self.single_chunk_3node, self.times_3node,
                                           self.members_3node, None)  # no test times
        expected = {
            'members': {
                '0': {
                    'times': self.times_3node,
                    'compared_values': [('SECONDARY', ), ('SECONDARY', )],
                    'labels': ('member 0 state', )
                }
            }
        }
        self.assertEqual(observed, expected)
        del rules.FLAG_MEMBER_STATES[2]

    def test_pri_not_found(self):
        """Test expected primary member cannot be found
        """
        primary = rules.find_primary(self.single_chunk_3node, self.members_3node)
        self.assertIsNone(primary)

    def test_pri_found(self):
        """Test expected primary member is found by chunk #4 (manually verified)
        """
        chunks_until_primary = 3
        for chunk in readers.read_ftdc(self.path_ftdc_3node_repl):
            primary = rules.find_primary(chunk, self.members_3node)
            if not chunks_until_primary:
                self.assertEqual(primary, '0')
                break
            else:
                self.assertIsNone(primary)
            chunks_until_primary -= 1

    def test_ftdc_replica_lag_check_success(self):  #pylint: disable=invalid-name
        """Test expected success for repl set secondary member lag check
        """
        path_ftdc = os.path.join(self.path_3shard_directory, 'metrics.3shard_p1_repl')
        perf_json = os.path.join(self.path_3shard_directory, 'perf.json')
        test_times = util.get_test_times(perf_json)
        observed = rules.ftdc_replica_lag_check(path_ftdc, test_times)
        expected = []
        self.assertEqual(observed, expected)

    def test_ftdc_replica_lag_check_fail(self):  #pylint: disable=invalid-name
        """Test expected failure for repl set secondary member lag check

           The diagnostic.data file metrics.mongod.0 contains ftdc data from the primary on a
           3 node replica set. In the data there are 4 distinct periods where replication lag will
           be above the threshold of 15 seconds, as you can see from the `expected` output object
           below. Note that unittest-files/test_repllag/failure_message.txt.ok contains the
           human readable failure message that corresponds to these replication lag failures.
        """
        path_ftdc = os.path.join(self.path_ftdc_repllag, 'metrics.mongod.0')
        perf_json = os.path.join(self.path_ftdc_repllag, 'perf.json')

        test_times = util.get_test_times(perf_json)
        observed = rules.ftdc_replica_lag_check(path_ftdc, test_times)
        expected = [{
            'additional': {
                'lag end threshold (s)': 2.0,
                'lag start threshold (s)': 15.0,
                'primary member': '0'
            },
            'members': {
                '1': {
                    'compared_values': [
                        (16.0, '2017-05-31 16:54:42Z', 129.0, '2017-05-31 16:54:42Z', 120.0),
                        (17.0, '2017-05-31 16:59:23Z', 104.0, '2017-05-31 16:59:26Z',
                         99.0), (16.0, '2017-05-31 17:04:33Z', 117.0, '2017-05-31 17:04:34Z',
                                 110.0), (16.0, '2017-05-31 17:09:13Z', 93.0,
                                          '2017-05-31 17:09:32Z', 12.0)
                    ],
                    'labels': ('start value (s)', 'max time', 'max value (s)', 'end time',
                               'end value (s)'),
                    'report_all_values':
                        True,
                    'times': [1496248949000, 1496249726000, 1496250019000, 1496250331000]
                },
                '2': {
                    'compared_values': [(16.0, '2017-05-31 16:54:03Z', 90.0, '2017-05-31 16:54:04Z',
                                         82.0), (16.0, '2017-05-31 16:58:53Z', 76.0,
                                                 '2017-05-31 16:59:00Z', 72.0),
                                        (16.0, '2017-05-31 17:03:53Z', 80.0, '2017-05-31 17:03:58Z',
                                         77.0), (16.0, '2017-05-31 17:08:53Z', 70.0,
                                                 '2017-05-31 17:08:54Z', 62.0)],
                    'labels': ('start value (s)', 'max time', 'max value (s)', 'end time',
                               'end value (s)'),
                    'report_all_values':
                        True,
                    'times': [1496248967000, 1496249735000, 1496250027000, 1496250339000]
                }
            }
        }]
        self.assertEqual(observed, expected)

    def test_lag_no_perf_file(self):
        """Test expected success when no test times are specified
        """
        path_ftdc_3shard = os.path.join(self.path_3shard_directory, 'metrics.3shard_p1_repl')
        observed = rules.ftdc_replica_lag_check(path_ftdc_3shard, None)
        expected = []
        self.assertEqual(observed, expected)


class TestFailureOutputFormatting(unittest.TestCase):
    """Test class checks resource sanity rules' error message formatting
    """

    def test_fail_collection_info(self):
        """Test expected output in _failure_collection when failure is detected
        """
        times = [1, 2, 3]
        compared_values = [(0, 1), (0, 3)]
        labels = ('label1', 'label2')
        additional = {'random_info': 1}
        observed = rules.failure_collection(times, compared_values, labels, additional)
        expected = {
            'times': times,
            'compared_values': compared_values,
            'labels': labels,
            'additional': additional
        }
        self.assertEqual(observed, expected)

    def test_fail_collection_empty(self):
        """Test expected output in _failure_collection when no failures detected
        """
        labels = ('label1', 'label2')
        observed = rules.failure_collection([], [], labels)
        expected = {}
        self.assertEqual(observed, expected)


class TestLogAnalysisRules(unittest.TestCase):
    """Test class evaluates correctness of mongod.log check rules
    """

    def test_is_log_line_bad(self):
        """Test `_is_log_line_bad()`."""

        bad_lines = [
            "2016-07-14T01:00:04.000+0000 F err-type foo bar baz",
            "2016-07-14T01:00:04.000+0000 E err-type foo bar baz",
            "2016-07-14T01:00:04.000+0000 L err-type elecTIon suCCEeded",
            "2016-07-14T01:00:04.000+0000 D err-type transition TO PRIMARY",
            "2016-07-14T01:00:04.000+0000 I err-type PosIx_FallocaTE FailEd"
        ]

        good_lines = [
            "2016-07-14T01:00:04.000+0000 L err-type nothing bad here",
            "2016-07-14T01:00:04.000+0000 L err-type or here",
            "2016-07-14T01:00:04.000+0000 E err-type ttl query execution for index"
        ]

        for line in bad_lines:
            self.assertTrue(rules.is_log_line_bad(line))

        for line in good_lines:
            self.assertFalse(rules.is_log_line_bad(line))

    def test_is_log_line_bad_time(self):
        """Test `_is_log_line_bad()` when test times are specified."""

        test_times = [
            (date_parser.parse("2016-07-14T01:00:00.000+0000"),
             date_parser.parse("2016-07-14T01:10:00.000+0000")),
            (date_parser.parse("2016-07-14T03:00:00.000+0000"),
             date_parser.parse("2016-07-14T03:10:00.000+0000")),
            (date_parser.parse("2016-07-14T05:00:00.999+0000"),
             date_parser.parse("2016-07-14T05:10:00.000+0000")),
        ]

        # last 2 times are the same time as test start / end (i.e. the times are inclusive)
        bad_lines = [
            "2016-07-14T01:00:04.000+0000 F err-type message",
            "2016-07-14T01:09:00.000+0000 F err-type message",
            "2016-07-14T03:05:00.000+0000 F err-type message",
            "2016-07-14T05:00:00.999+0000 F err-type message",
            "2016-07-14T05:10:00.000+0000 F err-type message"
        ]

        # last 2 times are just before and after the test started
        bad_lines_to_ignore = [
            "2016-07-14T00:05:00.000+0000 F err-type message",
            "2016-07-14T02:00:00.000+0000 F err-type message",
            "2016-07-14T03:25:00.000+0000 F err-type message",
            "2016-07-14T05:00:00.998+0000 F err-type message",
            "2016-07-14T05:10:00.001+0000 F err-type message"
        ]

        for line in bad_lines:
            self.assertTrue(rules.is_log_line_bad(line, test_times))

        for line in bad_lines_to_ignore:
            self.assertFalse(rules.is_log_line_bad(line, test_times))


class TestDBCorrectnessRules(unittest.TestCase):
    """Test class evaluates correctness of DB correctness check rules.
    """

    def test_dbcorrect_success(self):
        """Test expected success in db correctness test log file parsing
        """
        log_dir = test_utils.fixture_file_path('core_workloads_reports')
        expected_results = [{
            'status': 'pass',
            'start': 0,
            'log_raw': ('\nPassed db-hash-check.core_workloads_reports JS test.'),
            'test_file': 'db-hash-check.core_workloads_reports',
            'exit_code': 0
        }, {
            'status':
                'pass',
            'start':
                0,
            'log_raw': (
                '\nPassed validate-indexes-and-collections.core_workloads_reports JS test.'),
            'test_file': ('validate-indexes-and-collections.core_workloads_reports'),
            'exit_code':
                0
        }]
        observed_results = rules.db_correctness_analysis(log_dir)
        self.assertEqual(expected_results, observed_results)

    def test_dbcorrect_fail(self):
        """Test expected failure in db correctness test log file parsing
        """
        log_dir = test_utils.fixture_file_path('test_db_correctness')
        raw_failure = ('\nFAILURE: (logfile `localhost--localhost`)\n'
                       '2016-08-03T15:04:55.395-0400 E QUERY    [thread1] '
                       'Error: Collection validation failed :\n@(shell eval):1:20\n'
                       '@(shell eval):1:2\n\nFailed to run JS test on server [localhost], '
                       'host [localhost]\n1')
        expected_results = [{
            'status': 'fail',
            'start': 0,
            'log_raw': raw_failure,
            'test_file': 'validate-indexes-and-collections.test_db_correctness',
            'exit_code': 1
        }]
        observed_results = rules.db_correctness_analysis(log_dir)
        self.assertEqual(expected_results, observed_results)

    def test_dbcorrect_no_exit_code(self):
        """Test expected failure in db correctness test log file missing integer exit status
        """
        log_dir = test_utils.fixture_file_path('test_db_correctness_exit_fail')
        raw_failure = ('\nFAILURE: logfile `localhost--localhost` did not record a valid exit '
                       'code. Output:\n 2016-08-03T15:04:55.395-0400 E QUERY    [thread1] '
                       'Error: Collection validation failed :\n@(shell eval):1:20\n'
                       '@(shell eval):1:2\n\nFailed to run JS test on server [localhost], '
                       'host [localhost]')

        expected_results = [{
            'status': 'fail',
            'start': 0,
            'log_raw': raw_failure,
            'test_file': ('validate-indexes-and-collections.test_db_correctness_exit_fail'),
            'exit_code': 1
        }]
        observed_results = rules.db_correctness_analysis(log_dir)
        self.assertEqual(expected_results, observed_results)

    def test_no_jstests_run(self):
        """Test expected empty result when no db correctness checks are made
        """
        log_dir = test_utils.fixture_file_path('test_log_analysis')
        expected_results = []
        observed_results = rules.db_correctness_analysis(log_dir)
        self.assertEqual(expected_results, observed_results)


if __name__ == '__main__':
    unittest.main()
