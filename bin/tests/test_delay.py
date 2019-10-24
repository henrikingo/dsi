import unittest
from mock import MagicMock, call, patch
from delay import DelayNode, DelayError, DelayGraph, DelaySpec

BASIC_DELAY_CONFIG = {'default': {'delay_ms': 0, 'jitter_ms': 0}}


class DelayNodeTestCase(unittest.TestCase):
    def test_empty_node(self):
        node = DelayNode()

        expected = ["uname -r | cut -d '.' -f 1 | grep -q '4'", "sudo tc qdisc del dev eth0 root"]

        # We only test that the actual comman strings are the same
        # because the exception behavior is tested separately.
        actual = node.generate_commands()
        self.assertEqual(len(actual), len(expected))
        for i in xrange(len(expected)):
            self.assertEqual(actual[i].command, expected[i])

    def test_zero_delays(self):
        zero_delay_spec = DelaySpec({'delay_ms': 0, 'jitter_ms': 0})
        node = DelayNode()
        node.add("fake_ip_str_1", zero_delay_spec)
        node.add("fake_ip_str_2", zero_delay_spec)
        node.add("fake_ip_str_3", zero_delay_spec)

        expected = ["uname -r | cut -d '.' -f 1 | grep -q '4'", "sudo tc qdisc del dev eth0 root"]

        actual = node.generate_commands()
        self.assertEqual(len(actual), len(expected))
        for i in xrange(len(expected)):
            self.assertEqual(actual[i].command, expected[i])

    def test_one_nonzero_delay(self):
        node = DelayNode()
        zero_delay_spec = DelaySpec({'delay_ms': 0, 'jitter_ms': 0})
        nonzero_delay_spec = DelaySpec({'delay_ms': 100, 'jitter_ms': 5})
        node.add("fake_ip_str_1", zero_delay_spec)
        node.add("fake_ip_str_2", nonzero_delay_spec)
        node.add("fake_ip_str_3", zero_delay_spec)

        expected = [
            "uname -r | cut -d '.' -f 1 | grep -q '4'", "sudo tc qdisc del dev eth0 root",
            "sudo tc qdisc add dev eth0 root handle 1: htb default 1",
            "sudo tc class add dev eth0 parent 1: classid 1:1 htb rate 100tbit prio 0",
            "sudo tc class add dev eth0 parent 1: classid 1:2 htb rate 100tbit prio 0",
            "sudo tc qdisc add dev eth0 parent 1:2 netem delay 0ms 0ms",
            "sudo tc filter add dev eth0 protocol ip parent 1:0 prio 1 u32 match ip dst fake_ip_str_1 flowid 1:2",
            "sudo tc class add dev eth0 parent 1: classid 1:3 htb rate 100tbit prio 0",
            "sudo tc qdisc add dev eth0 parent 1:3 netem delay 100ms 5ms",
            "sudo tc filter add dev eth0 protocol ip parent 1:0 prio 1 u32 match ip dst fake_ip_str_2 flowid 1:3",
            "sudo tc class add dev eth0 parent 1: classid 1:4 htb rate 100tbit prio 0",
            "sudo tc qdisc add dev eth0 parent 1:4 netem delay 0ms 0ms",
            "sudo tc filter add dev eth0 protocol ip parent 1:0 prio 1 u32 match ip dst fake_ip_str_3 flowid 1:4"
        ]

        actual = node.generate_commands()
        self.assertEqual(len(actual), len(expected))
        for i in xrange(len(expected)):
            self.assertEqual(actual[i].command, expected[i])

    def test_differing_delays(self):
        nonzero_delay_spec_1 = DelaySpec({'delay_ms': 200, 'jitter_ms': 30})
        nonzero_delay_spec_2 = DelaySpec({'delay_ms': 100, 'jitter_ms': 5})
        nonzero_delay_spec_3 = DelaySpec({'delay_ms': 500, 'jitter_ms': 50})
        nonzero_delay_spec_4 = DelaySpec({'delay_ms': 10, 'jitter_ms': 0})

        node = DelayNode()
        node.add("fake_ip_str_1", nonzero_delay_spec_1)
        node.add("fake_ip_str_2", nonzero_delay_spec_2)
        node.add("fake_ip_str_3", nonzero_delay_spec_3)
        node.add("fake_ip_str_4", nonzero_delay_spec_4)

        expected = [
            "uname -r | cut -d '.' -f 1 | grep -q '4'", "sudo tc qdisc del dev eth0 root",
            "sudo tc qdisc add dev eth0 root handle 1: htb default 1",
            "sudo tc class add dev eth0 parent 1: classid 1:1 htb rate 100tbit prio 0",
            "sudo tc class add dev eth0 parent 1: classid 1:2 htb rate 100tbit prio 0",
            "sudo tc qdisc add dev eth0 parent 1:2 netem delay 200ms 30ms",
            "sudo tc filter add dev eth0 protocol ip parent 1:0 prio 1 u32 match ip dst fake_ip_str_1 flowid 1:2",
            "sudo tc class add dev eth0 parent 1: classid 1:3 htb rate 100tbit prio 0",
            "sudo tc qdisc add dev eth0 parent 1:3 netem delay 100ms 5ms",
            "sudo tc filter add dev eth0 protocol ip parent 1:0 prio 1 u32 match ip dst fake_ip_str_2 flowid 1:3",
            "sudo tc class add dev eth0 parent 1: classid 1:4 htb rate 100tbit prio 0",
            "sudo tc qdisc add dev eth0 parent 1:4 netem delay 500ms 50ms",
            "sudo tc filter add dev eth0 protocol ip parent 1:0 prio 1 u32 match ip dst fake_ip_str_3 flowid 1:4",
            "sudo tc class add dev eth0 parent 1: classid 1:5 htb rate 100tbit prio 0",
            "sudo tc qdisc add dev eth0 parent 1:5 netem delay 10ms 0ms",
            "sudo tc filter add dev eth0 protocol ip parent 1:0 prio 1 u32 match ip dst fake_ip_str_4 flowid 1:5"
        ]
        actual = node.generate_commands()
        self.assertEqual(len(actual), len(expected))
        for i in xrange(len(expected)):
            self.assertEqual(actual[i].command, expected[i])

    def test_establish_delays_runs_commands(self):
        mocked_host = MagicMock()
        mocked_host.run = MagicMock()
        mocked_host.run.return_value = True

        nonzero_delay_spec_1 = DelaySpec({'delay_ms': 700, 'jitter_ms': 10})
        nonzero_delay_spec_2 = DelaySpec({'delay_ms': 300, 'jitter_ms': 0})

        delay = DelayNode()
        delay.add("fake_ip_1", nonzero_delay_spec_1)
        delay.add("fake_ip_2", nonzero_delay_spec_2)
        delay.establish_delays(mocked_host)

        expected_calls = [
            call("uname -r | cut -d '.' -f 1 | grep -q '4'"),
            call("sudo tc qdisc del dev eth0 root"),
            call("sudo tc qdisc add dev eth0 root handle 1: htb default 1"),
            call("sudo tc class add dev eth0 parent 1: classid 1:1 htb rate 100tbit prio 0"),
            call("sudo tc class add dev eth0 parent 1: classid 1:2 htb rate 100tbit prio 0"),
            call("sudo tc qdisc add dev eth0 parent 1:2 netem delay 700ms 10ms"),
            call(
                "sudo tc filter add dev eth0 protocol ip parent 1:0 prio 1 u32 match ip dst fake_ip_1 flowid 1:2"
            ),
            call("sudo tc class add dev eth0 parent 1: classid 1:3 htb rate 100tbit prio 0"),
            call("sudo tc qdisc add dev eth0 parent 1:3 netem delay 300ms 0ms"),
            call(
                "sudo tc filter add dev eth0 protocol ip parent 1:0 prio 1 u32 match ip dst fake_ip_2 flowid 1:3"
            ),
        ]

        self.assertEqual(mocked_host.run.call_count, len(expected_calls))
        mocked_host.run.assert_has_calls(expected_calls)

    def test_establish_delays_fails(self):
        mocked_host = MagicMock()

        def mocked_run(command):
            if command == "sudo tc qdisc add dev eth0 root handle 1: htb default 1":
                return False
            return True

        mocked_host.run = mocked_run

        nonzero_delay_spec_1 = DelaySpec({'delay_ms': 700, 'jitter_ms': 10})
        nonzero_delay_spec_2 = DelaySpec({'delay_ms': 300, 'jitter_ms': 0})

        delay = DelayNode()
        delay.add("fake_ip_1", nonzero_delay_spec_1)
        delay.add("fake_ip_2", nonzero_delay_spec_2)

        self.assertRaises(DelayError, delay.establish_delays, mocked_host)

    def test_assert_kernel_fails(self):
        mocked_host = MagicMock()

        def mocked_run(command):
            if command == "uname -r | cut -d '.' -f 1 | grep -q '4'":
                return False
            return True

        mocked_host.run = mocked_run

        nonzero_delay_spec_1 = DelaySpec({'delay_ms': 400, 'jitter_ms': 10})
        nonzero_delay_spec_2 = DelaySpec({'delay_ms': 100, 'jitter_ms': 50})

        delay = DelayNode()
        delay.add("fake_ip_1", nonzero_delay_spec_1)
        delay.add("fake_ip_2", nonzero_delay_spec_2)

        self.assertRaises(DelayError, delay.establish_delays, mocked_host)

    def test_already_defined_ip(self):
        delay = DelayNode()
        nonzero_delay_spec_1 = DelaySpec({'delay_ms': 700, 'jitter_ms': 10})
        nonzero_delay_spec_2 = DelaySpec({'delay_ms': 300, 'jitter_ms': 0})
        nonzero_delay_spec_3 = DelaySpec({'delay_ms': 200, 'jitter_ms': 0})
        delay.add("fake_ip_1", nonzero_delay_spec_1)
        delay.add("fake_ip_2", nonzero_delay_spec_2)
        self.assertRaises(DelayError, delay.add, "fake_ip_1", nonzero_delay_spec_3)

    def test_negative_delay(self):
        delay = DelayNode()
        nonzero_delay_spec_1 = DelaySpec({'delay_ms': 50, 'jitter_ms': 10})
        nonzero_delay_spec_2 = DelaySpec({'delay_ms': 10, 'jitter_ms': 0})
        negative_delay_spec = DelaySpec({'delay_ms': -20, 'jitter_ms': 5})
        delay.add("fake_ip_1", nonzero_delay_spec_1)
        delay.add("fake_ip_2", nonzero_delay_spec_2)
        self.assertRaises(DelayError, delay.add, "fake_ip_3", negative_delay_spec)

    def test_negative_jitter(self):
        delay = DelayNode()
        nonzero_delay_spec_1 = DelaySpec({'delay_ms': 10, 'jitter_ms': 3})
        nonzero_delay_spec_2 = DelaySpec({'delay_ms': 10, 'jitter_ms': 10})
        negative_jitter_spec = DelaySpec({'delay_ms': 50, 'jitter_ms': -5})
        delay.add("fake_ip_1", nonzero_delay_spec_1)
        delay.add("fake_ip_2", nonzero_delay_spec_2)
        self.assertRaises(DelayError, delay.add, "fake_ip_3", negative_jitter_spec)


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
