#!/usr/bin/env python
"""Tests for the mongodb_setup module"""
import mock
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(sys.path[0]), 'bin'))

import mongodb_setup

# Mock the remote host module.
mongodb_setup.RemoteHost = mock.MagicMock()


class TestHelperMethods(unittest.TestCase):

    def test_args_list(self):
        opts = {
            'a': 1,
            'b': 'string',
            'c': None,
            'setParameters': {
                'a': 1,
                'b': 'string'
            }
        }
        expected_args = {
            '--a=1',
            '--b=string',
            '--c',
            '--setParameter=a=1',
            '--setParameter=b=string'
        }
        self.assertSetEqual(set(mongodb_setup.args_list(opts)), expected_args)

    def test_merge_dicts(self):
        base = {'a': 1, 'b': 'string'}
        override = {'b': 2, 'c': 3}
        expected_merge = {'a': 1, 'b': 2, 'c': 3}
        self.assertEqual(mongodb_setup.merge_dicts(base, override),
                         expected_merge)

    def test_merge_options(self):
        base = {
            'a': 1,
            'b': 'string',
            'setParameters': {
                'a': 1,
                'b': 'string'
            }
        }
        override = {
            'b': 2,
            'c': 3,
            'setParameters': {
                'b': 2,
                'c': 3
            }
        }
        expected_merge = {
            'a': 1,
            'b': 2,
            'c': 3,
            'setParameters': {
                'a': 1,
                'b': 2,
                'c': 3
            }
        }
        self.assertEqual(mongodb_setup.merge_options(base, override),
                         expected_merge)


class TestMongoNode(unittest.TestCase):

    def setUp(self):
        os.environ['SSHUSER'] = 'user'
        os.environ['PEMFILE'] = 'pem/file/path'
        self.mongo_node = mongodb_setup.MongoNode({
            'host': '1.2.3.4',
            'bin_dir': 'mongodb',
            'program_args': {
                'port': 9999,
                'storageEngine': 'wiredTiger',
                'oplogSize': 1024,
                'dbpath': '/tmp/db',
                'logpath': '/tmp/mongod.log',
                'setParameters': {
                    'enableTestCommands': 0
                }
            }
        })

    def test_hostport(self):
        self.assertEquals(self.mongo_node.hostport(), '1.2.3.4:9999')

    def test_launch_cmd(self):
        expected_args = {
            'mongodb/bin/mongod',
            '--fork',
            '--port=9999',
            '--dbpath=/tmp/db',
            '--oplogSize=1024',
            '--logpath=/tmp/mongod.log',
            '--storageEngine=wiredTiger',
            '--setParameter=enableTestCommands=0'
        }
        self.assertSetEqual(set(self.mongo_node.launch_cmd()),
                            expected_args)

    def test_mongo_shell_cmd(self):
        file_path = '/tmp/mongo_port_9999.js'
        expected_args = {
            'mongodb/bin/mongo',
            '--verbose',
            '--port=9999',
            file_path
        }
        self.assertSetEqual(set(self.mongo_node.mongo_shell_cmd(file_path)),
                            expected_args)


class TestReplSet(unittest.TestCase):

    def setUp(self):
        os.environ['SSHUSER'] = 'user'
        os.environ['PEMFILE'] = 'pem/file/path'

    def test_is_any_priority_set(self):
        repl_set_opts = {
            'name': 'rs',
            'node_opts': [
                {'host': '1.2.3.4'},
                {'host': '1.2.3.5'}
            ]
        }
        replSet = mongodb_setup.ReplSet(repl_set_opts)
        self.assertEquals(replSet.is_any_priority_set(), False)
        repl_set_opts['node_opts'][1]['priority'] = 5
        replSet = mongodb_setup.ReplSet(repl_set_opts)
        self.assertEquals(replSet.is_any_priority_set(), True)


    def test_highest_priority_node(self):
        repl_set_opts = {
            'name': 'rs',
            'node_opts': [
                {'host': '1.2.3.4'},
                {'host': '1.2.3.5'}
            ]
        }
        replSet = mongodb_setup.ReplSet(repl_set_opts)
        self.assertEquals(replSet.highest_priority_node(), replSet.nodes[0])
        repl_set_opts['node_opts'][1]['priority'] = 5
        replSet = mongodb_setup.ReplSet(repl_set_opts)
        self.assertEquals(replSet.highest_priority_node(), replSet.nodes[1])


if __name__ == '__main__':
    unittest.main()
