"""Tests for bin/common/config.py"""
import unittest

import logging
from mock import patch, call, ANY
from testfixtures import LogCapture

import common
import common.delays as delays
from common.models.host_info import HostInfo
import test_lib.structlog_for_test as structlog_for_test


class DelaysTestCase(unittest.TestCase):
    """Unit tests for network delays."""
    def setUp(self):
        # Setup logging so that structlog uses stdlib, and LogCapture works
        structlog_for_test.setup_logging()

        self.config = {
            'infrastructure_provisioning': {
                'tfvars': {
                    'image': 'amazon2',
                    'ssh_user': 'test_username',
                    'ssh_key_file': 'test_keyfile'
                },
                'network_delays': {
                    'interface': 'eth0',
                    'sys_configs': {
                        'amazon2': {
                            'rate': '100tbit'
                        }
                    }
                },
                'out': {
                    'workload_client': [{
                        'private_ip': '10.11.12.200',
                        'public_ip': '1.2.3.100'
                    }],
                    'mongod': [{
                        'private_ip': '10.11.12.13',
                        'public_ip': '1.2.3.4'
                    }, {
                        'private_ip': '10.11.12.14',
                        'public_ip': '1.2.3.5'
                    }, {
                        'private_ip': '10.11.12.15',
                        'public_ip': '1.2.3.6'
                    }]
                }
            }
        }
        self.command = {
            'network_delays': {
                'delay_ms':
                    60,
                'jitter_ms':
                    0,
                'groups': [{
                    'hosts': ['10.11.12.13', '10.11.12.14', '10.11.12.200'],
                    'delay_ms': 10
                }, {
                    'hosts': ['10.11.12.15', '10.11.12.200'],
                    'delay_ms': 5
                }]
            }
        }

    @patch('paramiko.SSHClient')
    @patch('common.remote_ssh_host.RemoteSSHHost.run')
    def test_establish(self, mock_run, mock_ssh):
        host_info = HostInfo(public_ip='1.2.3.4',
                             private_ip='10.11.12.13',
                             ssh_user='test_username',
                             ssh_key_file='test_keyfile',
                             category='mongod',
                             offset=0)
        target_host = common.host_factory.make_host(host_info)

        delays.establish_host_delays(target_host, self.command, self.config, None)

        expected_calls = [
            call([
                'bash', '-c',
                "'sudo tc qdisc del dev eth0 root' 2>&1 | grep -v 'RTNETLINK answers: No such file or directory'"
            ],
                 quiet=True),
            call(['bash', '-c', "'sudo tc qdisc add dev eth0 root handle 1: htb default 1'"]),
            call().__bool__(),
            call([
                'bash', '-c',
                "'sudo tc class add dev eth0 parent 1: classid 1:1 htb rate 100tbit prio 0'"
            ]),
            call().__bool__(),
            call([
                'bash', '-c',
                "'sudo tc class add dev eth0 parent 1: classid 1:2 htb rate 100tbit prio 0'"
            ]),
            call().__bool__(),
            call(['bash', '-c', "'sudo tc qdisc add dev eth0 parent 1:2 netem delay 10ms 0ms'"]),
            call().__bool__(),
            call([
                'bash', '-c',
                "'sudo tc filter add dev eth0 protocol ip parent 1:0 prio 1 u32 match ip dst 10.11.12.200 flowid 1:2'"
            ]),
            call().__bool__(),
            call([
                'bash', '-c',
                "'sudo tc class add dev eth0 parent 1: classid 1:3 htb rate 100tbit prio 0'"
            ]),
            call().__bool__(),
            call(['bash', '-c', "'sudo tc qdisc add dev eth0 parent 1:3 netem delay 10ms 0ms'"]),
            call().__bool__(),
            call([
                'bash', '-c',
                "'sudo tc filter add dev eth0 protocol ip parent 1:0 prio 1 u32 match ip dst 10.11.12.14 flowid 1:3'"
            ]),
            call().__bool__(),
            call([
                'bash', '-c',
                "'sudo tc class add dev eth0 parent 1: classid 1:4 htb rate 100tbit prio 0'"
            ]),
            call().__bool__(),
            call(['bash', '-c', "'sudo tc qdisc add dev eth0 parent 1:4 netem delay 60ms 0ms'"]),
            call().__bool__(),
            call([
                'bash', '-c',
                "'sudo tc filter add dev eth0 protocol ip parent 1:0 prio 1 u32 match ip dst 10.11.12.15 flowid 1:4'"
            ]),
            call().__bool__()
        ]
        mock_run.assert_has_calls(expected_calls)

    @patch('paramiko.SSHClient')
    @patch('common.remote_ssh_host.RemoteSSHHost.run')
    def test_establish_error(self, mock_run, mock_ssh):
        mock_run.return_value = False
        host_info = HostInfo(public_ip='1.2.3.4',
                             private_ip='10.11.12.13',
                             ssh_user='test_username',
                             ssh_key_file='test_keyfile',
                             category='mongod',
                             offset=0)
        target_host = common.host_factory.make_host(host_info)

        with self.assertRaises(delays.DelayError):
            delays.establish_host_delays(target_host, self.command, self.config, None)

    @patch('paramiko.SSHClient')
    @patch('common.remote_ssh_host.RemoteSSHHost.run')
    def test_reset(self, mock_run, mock_ssh):
        delays.reset_all_delays(self.config)

        expected_calls = [
            call([
                'bash', '-c',
                "'sudo tc qdisc del dev eth0 root' 2>&1 | grep -v 'RTNETLINK answers: No such file or directory'"
            ],
                 quiet=True),
            call([
                'bash', '-c',
                "'sudo tc qdisc del dev eth0 root' 2>&1 | grep -v 'RTNETLINK answers: No such file or directory'"
            ],
                 quiet=True),
            call([
                'bash', '-c',
                "'sudo tc qdisc del dev eth0 root' 2>&1 | grep -v 'RTNETLINK answers: No such file or directory'"
            ],
                 quiet=True),
            call([
                'bash', '-c',
                "'sudo tc qdisc del dev eth0 root' 2>&1 | grep -v 'RTNETLINK answers: No such file or directory'"
            ],
                 quiet=True)
        ]
        mock_run.assert_has_calls(expected_calls)

    @patch('paramiko.SSHClient')
    @patch('common.remote_ssh_host.RemoteSSHHost.run')
    def test_safe_reset_exception(self, mock_run, mock_ssh):
        mock_run.side_effect = Exception("mock exception")
        expected_log = ('common.delays', 'ERROR', ANY)

        with LogCapture(level=logging.ERROR) as log_output:
            delays.safe_reset_all_delays(self.config)
            log_output.check(expected_log)
