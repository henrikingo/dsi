#!/usr/bin/env python
"""Tests for the mongodb_setup module"""
import os
import sys
import unittest

import mock

sys.path.insert(0, os.path.join(os.path.dirname(sys.path[0]), 'bin'))

import mongodb_setup

# Mock the remote host module.
mongodb_setup.RemoteHost = mock.MagicMock()

MONGOD_OPTS = {
    'public_ip': '1.2.3.4',
    'mongo_dir': '/usr/',
    'config_file': {
        'systemLog': {
            'path': 'mongod.log'
        },
        'storage': {
            'dbPath': 'db'
        },
        'net': {
            'port': 9999
        }
    },
    'rs_conf_member': {}
}


class TestHelperFunctions(unittest.TestCase):
    """Basic tests for helper functions in mongodb_setup"""

    def test_args_list(self):
        """Test args_list correctly formats arguments"""
        opts = {'a': 1, 'b': 'string', 'c': None, 'setParameters': {'a': 1, 'b': 'string'}}
        expected_args = {
            '--a=1', '--b=string', '--c', '--setParameter=a=1', '--setParameter=b=string'
        }
        self.assertSetEqual(set(mongodb_setup.args_list(opts)), expected_args)

    def test_merge_dicts(self):
        """Test merge_dicts correctly overrides literals."""
        base = {'a': 1, 'b': 'string'}
        override = {'b': 2, 'c': 3}
        expected_merge = {'a': 1, 'b': 2, 'c': 3}
        self.assertEqual(mongodb_setup.merge_dicts(base, override), expected_merge)

    def test_merge_dicts_nested(self):
        """Test merge_dicts correctly overrides dictionaries."""
        base = {'a': 1, 'b': 'string', 'setParameters': {'a': 1, 'b': 'string'}}
        override = {'b': 2, 'c': 3, 'setParameters': {'b': 2, 'c': 3}}
        expected_merge = {'a': 1, 'b': 2, 'c': 3, 'setParameters': {'a': 1, 'b': 2, 'c': 3}}
        self.assertEqual(mongodb_setup.merge_dicts(base, override), expected_merge)


class TestMongoNode(unittest.TestCase):
    """MongoNode tests"""

    def setUp(self):
        """Create a MongoNode instance to use throughout tests."""
        self.mongo_node = mongodb_setup.MongoNode(mongodb_setup.copy_obj(MONGOD_OPTS))

    def test_hostport(self):
        """Test hostport format"""
        self.assertEquals(self.mongo_node.hostport_private(), '1.2.3.4:9999')

    def test_launch_cmd(self):
        """Test launch command uses proper config file."""
        expected_cmd = "/usr/bin/mongod --config /tmp/mongo_port_9999.conf"
        self.assertEqual(self.mongo_node.launch_cmd(), expected_cmd)

        self.mongo_node.numactl_prefix = "numactl --interleave=all --cpunodebind=1"
        expected_cmd = "numactl --interleave=all --cpunodebind=1 " + expected_cmd
        self.assertEqual(self.mongo_node.launch_cmd(), expected_cmd)


class TestReplSet(unittest.TestCase):
    """ReplSet tests"""

    def test_is_any_priority_set(self):
        """Test priority handling."""
        repl_set_opts = {
            'name': 'rs',
            'mongod': [mongodb_setup.copy_obj(MONGOD_OPTS),
                       mongodb_setup.copy_obj(MONGOD_OPTS)]
        }
        replset = mongodb_setup.ReplSet(repl_set_opts)
        self.assertEquals(replset.is_any_priority_set(), False)
        repl_set_opts['mongod'][1]['rs_conf_member']['priority'] = 5
        replset = mongodb_setup.ReplSet(repl_set_opts)
        self.assertEquals(replset.is_any_priority_set(), True)

    def test_highest_priority_node(self):
        """Test priority handling."""
        repl_set_opts = {
            'name': 'rs',
            'mongod': [mongodb_setup.copy_obj(MONGOD_OPTS),
                       mongodb_setup.copy_obj(MONGOD_OPTS)]
        }
        replset = mongodb_setup.ReplSet(repl_set_opts)
        self.assertEquals(replset.highest_priority_node(), replset.nodes[0])
        repl_set_opts['mongod'][1]['rs_conf_member']['priority'] = 5
        replset = mongodb_setup.ReplSet(repl_set_opts)
        self.assertEquals(replset.highest_priority_node(), replset.nodes[1])


class TestMongodbSetup(unittest.TestCase):
    """MongodbSetup tests"""

    def setUp(self):
        """Common options"""
        self.config = {
            'infrastructure_provisioning': {
                'tfvars': {
                    'ssh_user': 'ec2-user',
                    'ssh_key_file': '~/.ssh/user_ssh_key.pem'
                },
                'numactl_prefix': 'numactl test'
            },
            'mongodb_setup': {
                'shutdown_options': {
                    'force': True,
                    'timeoutSecs': 5
                },
                'journal_dir':
                    '/data/journal',
                'topology': [{
                    'cluster_type': 'standalone',
                    'id': 'myid1',
                    'public_ip': '1.2.3.4',
                    'private_ip': '10.2.0.1',
                    'config_file': {
                        'net': {
                            'port': 27017,
                            'bindIp': '0.0.0.0'
                        },
                        'storage': {
                            'dbPath': 'data/dbs',
                            'engine': 'wiredTiger'
                        },
                        'systemLog': {
                            'destination': 'file',
                            'path': 'data/logs/mongod.log'
                        }
                    }
                }]
            }
        }

    #pylint: disable=unused-argument
    @mock.patch('mongodb_setup.DownloadMongodb')
    def test_ssh_key(self, mock_downloader):
        """Test ~/.ssh/user_aws_key.pem"""
        mongodb_setup.MongodbSetup(self.config, mock.Mock())
        ssh_key_file = self.config['infrastructure_provisioning']['tfvars']['ssh_key_file']
        expected_ssh_key_file = os.path.expanduser(ssh_key_file)
        self.assertEquals(mongodb_setup.MongoNode.ssh_key_file, expected_ssh_key_file)
        self.assertEquals(mongodb_setup.MongoNode.ssh_user, 'ec2-user')


if __name__ == '__main__':
    unittest.main()
