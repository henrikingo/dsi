#!/usr/bin/env python
"""Tests for the mongodb_setup module"""
import os
import sys
import unittest

import mock

sys.path.insert(0, os.path.join(os.path.dirname(sys.path[0]), 'bin'))

import mongodb_setup  # pylint: disable=import-error

# Mock the remote host module.
mongodb_setup.RemoteHost = mock.MagicMock()

MONGOD_OPTS = {
    'public_ip': '1.2.3.4',
    'mongo_dir': '/usr/',
    'config_file': {
        'systemLog': {'path': 'mongod.log'},
        'storage': {'dbPath': 'db'},
        'net': {'port': 9999}
    }
}


class TestHelperFunctions(unittest.TestCase):
    """Basic tests for helper functions in mongodb_setup"""

    def test_args_list(self):
        """Test args_list correctly formats arguments"""
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
        """Test merge_dicts correctly overrides literals."""
        base = {'a': 1, 'b': 'string'}
        override = {'b': 2, 'c': 3}
        expected_merge = {'a': 1, 'b': 2, 'c': 3}
        self.assertEqual(mongodb_setup.merge_dicts(base, override),
                         expected_merge)

    def test_merge_dicts_nested(self):
        """Test merge_dicts correctly overrides dictionaries."""
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
        self.assertEqual(mongodb_setup.merge_dicts(base, override),
                         expected_merge)


class TestMongoNode(unittest.TestCase):
    """MongoNode tests"""

    def setUp(self):
        """Create a MongoNode instance to use throughout tests."""
        self.mongo_node = mongodb_setup.MongoNode(MONGOD_OPTS.copy())

    def test_hostport(self):
        """Test hostport format"""
        self.assertEquals(self.mongo_node.hostport_private(), '1.2.3.4:9999')

    def test_launch_cmd(self):
        """Test launch command uses proper config file."""
        expected_argv = ['/usr/bin/mongod', '--config', '/tmp/mongo_port_9999.conf']
        self.assertEqual(self.mongo_node.launch_cmd(), expected_argv)

    def test_mongo_shell_cmd(self):
        """Test mongo_shell_cmd uses proper arguments."""
        file_path = '/tmp/mongo_port_9999.js'
        expected_argv = ['/usr/bin/mongo', '--verbose', '--port=9999', file_path]
        self.assertEqual(self.mongo_node.mongo_shell_cmd(file_path),
                         expected_argv)


class TestReplSet(unittest.TestCase):
    """ReplSet tests"""

    def test_is_any_priority_set(self):
        """Test priority handling."""
        repl_set_opts = {
            'name': 'rs',
            'mongod': [MONGOD_OPTS.copy(), MONGOD_OPTS.copy()]
        }
        replset = mongodb_setup.ReplSet(repl_set_opts)
        self.assertEquals(replset.is_any_priority_set(), False)
        repl_set_opts['mongod'][1]['priority'] = 5
        replset = mongodb_setup.ReplSet(repl_set_opts)
        self.assertEquals(replset.is_any_priority_set(), True)

    def test_highest_priority_node(self):
        """Test priority handling."""
        repl_set_opts = {
            'name': 'rs',
            'mongod': [MONGOD_OPTS.copy(), MONGOD_OPTS.copy()]
        }
        replset = mongodb_setup.ReplSet(repl_set_opts)
        self.assertEquals(replset.highest_priority_node(), replset.nodes[0])
        repl_set_opts['mongod'][1]['priority'] = 5
        replset = mongodb_setup.ReplSet(repl_set_opts)
        self.assertEquals(replset.highest_priority_node(), replset.nodes[1])


if __name__ == '__main__':
    unittest.main()
