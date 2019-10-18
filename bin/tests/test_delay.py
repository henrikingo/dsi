import unittest
from mock import patch, call
from delay import DelayGraph, DelaySpec

BASIC_DELAY_CONFIG = {'default': {'delay_ms': 0, 'jitter_ms': 0}}


class DelayGraphTestCase(unittest.TestCase):
    def test_parse_standalone(self):
        topology = {
            'cluster_type': 'standalone',
            'public_ip': '1.2.3.4',
            'private_ip': '10.2.0.1',
        }
        delay_graph = DelayGraph(topology, BASIC_DELAY_CONFIG)
        expected = ['10.2.0.1']
        for private_ip in delay_graph.graph:
            self.assertTrue(private_ip in expected)
        self.assertEqual(len(expected), len(delay_graph.graph))

    def test_parse_replset(self):
        topology = {
            'cluster_type':
                'replset',
            'mongod': [{
                'public_ip': '1.2.3.4',
                'private_ip': '10.2.0.1'
            }, {
                'public_ip': '2.3.4.5',
                'private_ip': '10.2.0.2'
            }, {
                'public_ip': '3.4.5.6',
                'private_ip': '10.2.0.3'
            }]
        }
        delay_graph = DelayGraph(topology, BASIC_DELAY_CONFIG)
        expected = ['10.2.0.1', '10.2.0.2', '10.2.0.3']
        for private_ip in delay_graph.graph:
            self.assertTrue(private_ip in expected)
        self.assertEqual(len(expected), len(delay_graph.graph))

    def test_parse_sharded(self):
        topology = {
            'cluster_type':
                'sharded_cluster',
            'configsvr': [{
                'public_ip': '1.2.3.4',
                'private_ip': '10.2.0.1'
            }, {
                'public_ip': '2.3.4.5',
                'private_ip': '10.2.0.2'
            }, {
                'public_ip': '3.4.5.6',
                'private_ip': '10.2.0.3'
            }],
            'mongos': [{
                'public_ip': '6.7.8.9',
                'private_ip': '10.2.0.4'
            }, {
                'public_ip': '7.8.9.10',
                'private_ip': '10.2.0.5'
            }, {
                'public_ip': '8.9.10.11',
                'private_ip': '10.2.0.6'
            }],
            'shard': [{
                'cluster_type':
                    'replset',
                'mongod': [{
                    'public_ip': '9.10.11.12',
                    'private_ip': '10.2.0.7'
                }, {
                    'public_ip': '10.11.12.13',
                    'private_ip': '10.2.0.8'
                }, {
                    'public_ip': '11.12.13.14',
                    'private_ip': '10.2.0.9'
                }]
            }, {
                'cluster_type':
                    'replset',
                'mongod': [{
                    'public_ip': '12.13.14.15',
                    'private_ip': '10.2.0.10'
                }, {
                    'public_ip': '13.14.15.16',
                    'private_ip': '10.2.0.11'
                }, {
                    'public_ip': '14.15.16.17',
                    'private_ip': '10.2.0.12'
                }]
            }, {
                'cluster_type':
                    'replset',
                'mongod': [{
                    'public_ip': '15.16.17.18',
                    'private_ip': '10.2.0.13'
                }, {
                    'public_ip': '16.17.18.19',
                    'private_ip': '10.2.0.14'
                }, {
                    'public_ip': '17.18.19.20',
                    'private_ip': '10.2.0.15'
                }]
            }]
        }
        delay_graph = DelayGraph(topology, BASIC_DELAY_CONFIG)
        expected = ['10.2.0.{num}'.format(num=i) for i in xrange(1, 16)]
        for private_ip in delay_graph.graph:
            self.assertTrue(private_ip in expected)
        self.assertEqual(len(expected), len(delay_graph.graph))

    @patch('delay.DelayNode')
    def test_zero_default_delays(self, mocked_delay_node):
        topology = {
            'cluster_type':
                'replset',
            'mongod': [{
                'public_ip': '1.2.3.4',
                'private_ip': '10.2.0.1'
            }, {
                'public_ip': '2.3.4.5',
                'private_ip': '10.2.0.2'
            }, {
                'public_ip': '3.4.5.6',
                'private_ip': '10.2.0.3'
            }]
        }
        delay_graph = DelayGraph(topology, BASIC_DELAY_CONFIG)
        self.assertEqual(len(delay_graph.graph), 3)
        default_delay_spec = DelaySpec({'delay_ms': 0, 'jitter_ms': 0})
        self.assertEqual(delay_graph.default_delay.delay_ms, default_delay_spec.delay_ms)
        self.assertEqual(delay_graph.default_delay.jitter_ms, default_delay_spec.jitter_ms)

        # Each IP gets called twice: once for each of the other nodes.
        expected = [
            call('10.2.0.1', delay_graph.default_delay),
            call('10.2.0.1', delay_graph.default_delay),
            call('10.2.0.2', delay_graph.default_delay),
            call('10.2.0.2', delay_graph.default_delay),
            call('10.2.0.3', delay_graph.default_delay),
            call('10.2.0.3', delay_graph.default_delay),
        ]
        self.assertEqual(mocked_delay_node.return_value.add.call_count, len(expected))
        mocked_delay_node.return_value.add.assert_has_calls(expected, any_order=True)

    @patch('delay.DelayNode')
    def test_nonzero_default_delays(self, mocked_delay_node):
        topology = {
            'cluster_type':
                'replset',
            'mongod': [{
                'public_ip': '1.2.3.4',
                'private_ip': '10.2.0.1'
            }, {
                'public_ip': '2.3.4.5',
                'private_ip': '10.2.0.2'
            }, {
                'public_ip': '3.4.5.6',
                'private_ip': '10.2.0.3'
            }]
        }
        delay_config = {'default': {'delay_ms': 100, 'jitter_ms': 10}}

        delay_graph = DelayGraph(topology, delay_config)
        self.assertEqual(len(delay_graph.graph), 3)
        delay_spec = DelaySpec({'delay_ms': 100, 'jitter_ms': 10})
        self.assertEqual(delay_graph.default_delay.delay_ms, delay_spec.delay_ms)
        self.assertEqual(delay_graph.default_delay.jitter_ms, delay_spec.jitter_ms)

        # Each IP gets called twice: once for each of the other nodes.
        expected = [
            call('10.2.0.1', delay_graph.default_delay),
            call('10.2.0.1', delay_graph.default_delay),
            call('10.2.0.2', delay_graph.default_delay),
            call('10.2.0.2', delay_graph.default_delay),
            call('10.2.0.3', delay_graph.default_delay),
            call('10.2.0.3', delay_graph.default_delay),
        ]
        self.assertEqual(mocked_delay_node.return_value.add.call_count, len(expected))
        mocked_delay_node.return_value.add.assert_has_calls(expected, any_order=True)
