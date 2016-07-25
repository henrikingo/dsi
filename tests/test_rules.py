"""Unit tests for the rules module. Run using nosetests."""

import unittest

import readers
import rules
from tests import test_utils

class TestRules(unittest.TestCase):
    """Test class evaluates correctness of resource sanity check rules.
    """

    def setUp(self):
        """Specifies the paths used to fetch JSON testing files. Additionally,
        sets up the common parameters for each operation being tested.
        """
        # parameters used in test cases
        self.path_ftdc_3node_repl = '{0}linux_3node_replSet_p1.ftdc.metrics'.format(
            test_utils.FIXTURE_DIR_PATH)
        self.single_chunk_3node = self._first_chunk(self.path_ftdc_3node_repl)
        self.times_3node = self.single_chunk_3node[rules.FTDC_KEYS['time']]
        self.members_3node = ['0', '1', '2']

        path_ftdc_standalone = '{0}core_workloads_wt.ftdc.metrics'.format(
            test_utils.FIXTURE_DIR_PATH)
        self.single_chunk_standalone = self._first_chunk(path_ftdc_standalone)
        self.times_standalone = self.single_chunk_standalone[rules.FTDC_KEYS['time']]

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
        observed = rules.below_configured_cache_size(self.single_chunk_3node,
                                                     self.times_3node,
                                                     cache_max_3node)
        expected = {}
        self.assertEqual(observed, expected)

    def test_below_cache_max_fail(self):
        """Test expected failure for case of current cache size being above configured cache size
        """
        configured_cache_size = 100
        observed = rules.below_configured_cache_size(self.single_chunk_3node,
                                                     self.times_3node,
                                                     configured_cache_size)
        expected = {
            'times': self.times_3node,
            'compared_values': [(32554,), (32554,)],
            'labels': ('current cache size (bytes)',),
            'additional': {'WT configured cache size (bytes)': configured_cache_size}
        }
        self.assertEqual(observed, expected)

    def test_below_oplog_max_success(self):
        """Test expected success for case of current oplog size below configured oplog size
        """
        oplog_max_3node = 161061273600
        observed = rules.below_configured_oplog_size(self.single_chunk_3node,
                                                     self.times_3node,
                                                     oplog_max_3node)
        expected = {}
        self.assertEqual(observed, expected)

    def test_below_oplog_max_fail(self):
        """Test expected failure for case of current oplog size above configured oplog size
        """
        configured_oplog_size = 10
        observed = rules.below_configured_oplog_size(self.single_chunk_3node,
                                                     self.times_3node,
                                                     configured_oplog_size)
        expected = {
            'times': self.times_3node,
            'compared_values': [(86,), (86,)],
            'labels': ('current oplog size (MB)',),
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
                                                     self.times_standalone,
                                                     configured_oplog_size)
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
        observed = rules.compare_heap_cache_sizes(self.single_chunk_3node,
                                                  self.times_3node)
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
        observed = rules.max_connections(self.single_chunk_standalone,
                                         self.times_standalone,
                                         max_thread_level,
                                         [])
        expected = {}
        self.assertEqual(observed, expected)

    def test_max_connections_fail(self):
        """Test expected failure for current # connections above our specified upper bound
        """
        max_thread_level = 0
        observed = rules.max_connections(self.single_chunk_3node,
                                         self.times_3node,
                                         max_thread_level,
                                         self.members_3node)
        expected = {
            'times': self.times_3node,
            'compared_values': [(3,), (3,)],
            'labels': ('number of current connections',),
            'additional': {
                'max thread level for this task': max_thread_level,
                'rule': '# connections <= (max thread level + 6)'
            }
        }
        self.assertEqual(observed, expected)

    def test_member_state_success(self):
        """Test expected success for members all in 'healthy' states
        """
        observed = rules.repl_member_state(self.single_chunk_3node,
                                           self.times_3node,
                                           self.members_3node)
        expected = {}
        print observed
        self.assertEqual(observed, expected)

    def test_member_state_fail(self):
        """Test expected failure for member discovered in an 'unhealthy' state
        """
        rules.FLAG_MEMBER_STATES[2] = 'SECONDARY'
        observed = rules.repl_member_state(self.single_chunk_3node,
                                           self.times_3node,
                                           self.members_3node)
        expected = {
            'members':
                {'0': {'times': self.times_3node,
                       'compared_values': [('SECONDARY',), ('SECONDARY',)],
                       'labels': ('member 0 state',)}
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

    def test_fail_collection_empty(self):
        """Test expected output in _failure_collection when no failures detected
        """
        labels = ('label1', 'label2')
        observed = rules.failure_collection([], [], labels)
        expected = {}
        self.assertEqual(observed, expected)

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

if __name__ == '__main__':
    unittest.main()