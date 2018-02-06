#!/usr/bin/env python
"""Tests for the mongodb_setup module"""
import copy
import os
import os.path
import unittest

import mock

import mongodb_setup
import common.host

from tests.any_in_string import ANY_IN_STRING

# Mock the remote host module.
mongodb_setup.RemoteHost = mock.MagicMock()

MONGOD_OPTS = {
    'public_ip': '1.2.3.4',
    'mongo_dir': '/usr/',
    'config_file': {
        'net': {
            'port': 9999,
            'bindIp': '0.0.0.0'
        },
        'systemLog': {
            'destination': 'file',
            'path': 'mongod.log'
        },
        'storage': {
            'dbPath': 'data/dbs'
        },
    },
    'rs_conf_member': {}
}

DEFAULT_CONFIG = {
    'infrastructure_provisioning': {
        'tfvars': {
            'ssh_user': 'ec2-user',
            'ssh_key_file': '~/.ssh/user_ssh_key.pem'
        },
        'numactl_prefix': 'numactl test',
        'out': []
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
                    'port': 9999,
                    'bindIp': '0.0.0.0'
                },
                'storage': {
                    'dbPath': 'data/dbs',
                    'engine': 'wiredTiger'
                },
                'systemLog': {
                    'destination': 'file',
                    'path': 'mongod.log'
                }
            }
        }]
    }
}


class TestHelperFunctions(unittest.TestCase):
    """Basic tests for helper functions in mongodb_setup"""

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


# pylint: disable=too-many-public-methods
class TestMongoNode(unittest.TestCase):
    """MongoNode tests"""

    def setUp(self):
        """Create a MongoNode instance to use throughout tests."""
        topology = mongodb_setup.copy_obj(MONGOD_OPTS)
        self.topology = topology
        self.config = DEFAULT_CONFIG
        self.mongo_node = mongodb_setup.MongoNode(topology=topology, config=self.config)

    def test_run_mongo_shell(self):
        """Test hostport format"""

        mock_host = mock.MagicMock(name='host')
        self.mongo_node.host = mock_host
        mock_host.exec_mongo_command.return_value = 0
        self.assertTrue(self.mongo_node.run_mongo_shell('js command'))
        mock_host.exec_mongo_command.assert_called_once_with(
            'js command', '/tmp/mongo_port_9999.js', 'localhost:9999', max_time_ms=None)

        mock_host = mock.MagicMock(name='host')
        mock_dump_mongo_log = mock.MagicMock(name='dump_mongo_log')
        self.mongo_node.host = mock_host
        self.mongo_node.dump_mongo_log = mock_dump_mongo_log
        mock_host.exec_mongo_command.return_value = 1

        self.assertFalse(self.mongo_node.run_mongo_shell('js command', max_time_ms=1))
        mock_dump_mongo_log.assert_called_once()
        mock_host.exec_mongo_command.assert_called_once_with(
            'js command', '/tmp/mongo_port_9999.js', 'localhost:9999', max_time_ms=1)

    def test_hostport(self):
        """Test hostport format"""
        self.assertEquals(self.mongo_node.hostport_private(), '1.2.3.4:9999')

    def test_logdir(self):
        """Default log dir is empty"""
        self.assertEquals(self.mongo_node.logdir, '')

    def _commands_run_during_setup_host(self, restart_clean_db_dir=None, restart_clean_logs=None):
        """Returns list of (args,kwargs) tuples representing calls to `host.run`
        made during invocation of setup_host with the given setup_host_args."""
        host = mock.MagicMock()
        host.run.return_value = '<Expected>'
        self.mongo_node.host = host

        return_value = self.mongo_node.setup_host(
            restart_clean_db_dir=restart_clean_db_dir, restart_clean_logs=restart_clean_logs)
        calls = [args for (method, args, _) in host.method_calls if method == 'run']

        self.assertIs(len(calls), 1, "Only one call to host.run()")
        # calls is list of run method calls; calls[0] is (args,kwargs) tuple
        # https://docs.python.org/3/library/unittest.mock.html#calls-as-tuples
        return return_value, calls[0][0]

    def test_setup_host_defaults(self):
        """We issue the important `rm` commands when setup_host is called with default parameters"""
        return_value, commands_issued = self._commands_run_during_setup_host()
        self.assertEquals(
            return_value, '<Expected>',
            "Calling run() doesn't return None. " + "It returns what the host delegate returns.")

        required = [['rm', '-rf', a]
                    for a in [
                        '*.log', 'core.*', 'data/dbs/diagnostic.data/*', 'diagnostic.data',
                        'data/dbs', '/media/ephemeral1/journal'
                    ]]
        for req in required:
            self.assertTrue(req in commands_issued,
                            "Should have issued command %s in %s" % (req, commands_issued))

    def test_rm_commands_no_cleanup(self):
        """We don't issue any rm commands if we give False for clean_* params"""
        _, commands_issued = self._commands_run_during_setup_host(
            restart_clean_db_dir=False, restart_clean_logs=False)
        for command in commands_issued:
            self.assertNotIn('rm', command, "No rm commands in setup_host without clean_* args")

    def _test_setup_commands(self, generate_setup_commands_args, expected):
        """Runs _generate_setup_commands with given args
        and asserts the output == expected. If not, prints it out in a form
        that you can copy/paste into an 'expected' var"""
        # pylint: disable=protected-access
        actual = mongodb_setup.MongoNode._generate_setup_commands(generate_setup_commands_args)
        self.assertEquals(actual, expected, msg=",\n".join([str(x) for x in actual]))

    def test_ssh_key(self):
        """Test ~/.ssh/user_aws_key.pem"""
        ssh_key_file = self.config['infrastructure_provisioning']['tfvars']['ssh_key_file']
        expected_ssh_key_file = os.path.expanduser(ssh_key_file)

        node = mongodb_setup.MongoNode(
            topology=self.config['mongodb_setup']['topology'][0], config=self.config)
        # pylint: disable=protected-access
        (actual_user, actual_key) = node._ssh_user_and_key_file()
        self.assertEquals(actual_key, expected_ssh_key_file)
        self.assertEquals(actual_user, 'ec2-user')

    # below tests want to be named
    #     test_generate_setup_commands_*
    # by pylint doesn't like the method names
    #
    # Below we test each combination of clean_db_dir, clean_logs, and use_journal_mnt
    # to be True and False with ttt indicating that all are True, ttf indicating
    # that all are true except for use_journal_mount which is False, etc.

    def test_gen_setup_commands_ttt(self):
        """Proper output for _generate_setup_commands with
        clean_db_dir = True
        clean_logs = True
        use_journal_mnt = True
        is_mongos = True
        """
        self._test_setup_commands(
            {
                'clean_db_dir': True,
                'clean_logs': True,
                'use_journal_mnt': True,
                'is_mongos': True,
                'dbdir': 'some dir with spaces',
                'journal_dir': '$journal_dir',  # intentionally ugly
                'logdir': '/ log/di r//',
            },
            [['rm', '-rf', '/ log/di r//*.log'], ['rm', '-rf', '/ log/di r//core.*'], [
                'mkdir', '-p', '/ log/di r//'
            ], ['mkdir', '-p', 'some dir with spaces/diagnostic.data'], [
                'rm', '-rf', '/ log/di r//diagnostic.data'
            ], ['mv', 'some dir with spaces/diagnostic.data', '/ log/di r//'], [
                'rm', '-rf', 'some dir with spaces'
            ], ['rm', '-rf', '$journal_dir'], ['mkdir', '-p', 'some dir with spaces'], [
                'mv', '/ log/di r//diagnostic.data', 'some dir with spaces'
            ], ['mkdir', '-p', '$journal_dir'], [
                'ln', '-s', '$journal_dir', 'some dir with spaces/journal'
            ], ['ls', '-la', 'some dir with spaces'], ['ls', '-la']])

    def test_gen_setup_commands_ttf_t(self):
        """Proper output for _generate_setup_commands with
        clean_db_dir = True
        clean_logs = True
        use_journal_mnt = False
        is_mongos = True
        """
        self._test_setup_commands({
            'clean_db_dir': True,
            'clean_logs': True,
            'use_journal_mnt': False,
            'is_mongos': True,
            'dbdir': 'dbdir',
            'journal_dir': 'journaldir',
            'logdir': 'logdir',
        }, [['rm', '-rf', 'logdir/*.log'], ['rm', '-rf', 'logdir/core.*'],
            ['mkdir', '-p', 'logdir'], ['mkdir', '-p', 'dbdir/diagnostic.data'],
            ['rm', '-rf', 'logdir/diagnostic.data'], ['mv', 'dbdir/diagnostic.data', 'logdir'],
            ['rm', '-rf', 'dbdir'], ['mkdir', '-p', 'dbdir'],
            ['mv', 'logdir/diagnostic.data', 'dbdir'], ['ls', '-la', 'dbdir'], ['ls', '-la']])

    def test_gen_setup_commands_ttf_f(self):
        """Proper output for _generate_setup_commands with
        clean_db_dir = True
        clean_logs = True
        use_journal_mnt = False
        is_mongos = False
        """
        self._test_setup_commands({
            'clean_db_dir': True,
            'clean_logs': True,
            'use_journal_mnt': False,
            'is_mongos': False,
            'dbdir': 'dbdir',
            'journal_dir': 'journaldir',
            'logdir': 'logdir',
        }, [['rm', '-rf', 'logdir/*.log'], ['rm', '-rf', 'logdir/core.*'], [
            'rm', '-rf', 'dbdir/diagnostic.data/*'
        ], ['mkdir', '-p', 'logdir'], ['mkdir', '-p', 'dbdir/diagnostic.data'],
            ['rm', '-rf', 'logdir/diagnostic.data'], ['mv', 'dbdir/diagnostic.data', 'logdir'],
            ['rm', '-rf', 'dbdir'], ['mkdir', '-p', 'dbdir'],
            ['mv', 'logdir/diagnostic.data', 'dbdir'], ['ls', '-la', 'dbdir'], ['ls', '-la']])

    def test_gen_setup_commands_tft(self):
        """Proper output for _generate_setup_commands with
        clean_db_dir = True
        clean_logs = False
        use_journal_mnt = True
        is_mongos = True
        """
        self._test_setup_commands({
            'clean_db_dir': True,
            'clean_logs': False,
            'use_journal_mnt': True,
            'is_mongos': True,
            'dbdir': 'dbdir',
            'journal_dir': 'journaldir',
            'logdir': 'logdir',
        }, [['mkdir', '-p', 'logdir'], ['mkdir', '-p', 'dbdir/diagnostic.data'],
            ['rm', '-rf', 'logdir/diagnostic.data'], ['mv', 'dbdir/diagnostic.data', 'logdir'],
            ['rm', '-rf', 'dbdir'], ['rm', '-rf', 'journaldir'], ['mkdir', '-p', 'dbdir'],
            ['mv', 'logdir/diagnostic.data', 'dbdir'], ['mkdir', '-p', 'journaldir'],
            ['ln', '-s', 'journaldir', 'dbdir/journal'], ['ls', '-la', 'dbdir'], ['ls', '-la']])

    def test_gen_setup_commands_tff(self):
        """Proper output for _generate_setup_commands with
        clean_db_dir = True
        clean_logs = False
        use_journal_mnt = False
        is_mongos = True
        """
        self._test_setup_commands({
            'clean_db_dir': True,
            'clean_logs': False,
            'use_journal_mnt': False,
            'is_mongos': True,
            'dbdir': 'dbdir',
            'journal_dir': 'journaldir',
            'logdir': 'logdir',
        }, [['mkdir', '-p', 'logdir'], ['mkdir', '-p', 'dbdir/diagnostic.data'],
            ['rm', '-rf', 'logdir/diagnostic.data'], ['mv', 'dbdir/diagnostic.data', 'logdir'],
            ['rm', '-rf', 'dbdir'], ['mkdir', '-p', 'dbdir'],
            ['mv', 'logdir/diagnostic.data', 'dbdir'], ['ls', '-la', 'dbdir'], ['ls', '-la']])

    def test_gen_setup_commands_ftt(self):
        """Proper output for _generate_setup_commands with
        clean_db_dir = False
        clean_logs = True
        use_journal_mnt = True
        is_mongos = True
        """
        self._test_setup_commands({
            'clean_db_dir': False,
            'clean_logs': True,
            'use_journal_mnt': True,
            'is_mongos': True,
            'dbdir': 'dbdir',
            'journal_dir': 'journaldir',
            'logdir': 'logdir',
        }, [['rm', '-rf', 'logdir/*.log'], ['rm', '-rf', 'logdir/core.*'],
            ['mkdir', '-p', 'logdir'], ['ls', '-la']])

    def test_gen_setup_commands_ftf(self):
        """Proper output for _generate_setup_commands with
        clean_db_dir = False
        clean_logs = True
        use_journal_mnt = False
        is_mongos = True
        """
        self._test_setup_commands({
            'clean_db_dir': False,
            'clean_logs': True,
            'use_journal_mnt': False,
            'is_mongos': True,
            'dbdir': 'dbdir',
            'journal_dir': 'journaldir',
            'logdir': 'logdir',
        }, [['rm', '-rf', 'logdir/*.log'], ['rm', '-rf', 'logdir/core.*'],
            ['mkdir', '-p', 'logdir'], ['ls', '-la']])

    def test_gen_setup_commands_fft(self):
        """Proper output for _generate_setup_commands with
        clean_db_dir = False
        clean_logs = False
        use_journal_mnt = True
        is_mongos = True
        """
        self._test_setup_commands({
            'clean_db_dir': False,
            'clean_logs': False,
            'use_journal_mnt': True,
            'is_mongos': True,
            'dbdir': 'dbdir',
            'journal_dir': 'journaldir',
            'logdir': 'logdir',
        }, [['mkdir', '-p', 'logdir'], ['ls', '-la']])

    def test_gen_setup_commands_fff(self):
        """Proper output for _generate_setup_commands with
        clean_db_dir = False
        clean_logs = False
        use_journal_mnt = False
        is_mongos = True
        """
        self._test_setup_commands({
            'clean_db_dir': False,
            'clean_logs': False,
            'use_journal_mnt': False,
            'is_mongos': True,
            'dbdir': 'dbdir',
            'journal_dir': 'journaldir',
            'logdir': 'logdir',
        }, [['mkdir', '-p', 'logdir'], ['ls', '-la']])

    def test_launch_cmd(self):
        """Test launch command uses proper config file."""
        original_prefix = DEFAULT_CONFIG['infrastructure_provisioning']['numactl_prefix']
        modified_prefix = "numactl --interleave=all --cpunodebind=1"
        expected_cmd = "/usr/bin/mongod --config /tmp/mongo_port_9999.conf"

        self.assertEqual(self.mongo_node.launch_cmd(), original_prefix + " " + expected_cmd)

        modified_config = mongodb_setup.copy_obj(DEFAULT_CONFIG)
        modified_config['infrastructure_provisioning']['numactl_prefix'] = modified_prefix

        command_with_modified_prefix = mongodb_setup.MongoNode(self.topology,
                                                               modified_config).launch_cmd()

        self.assertEqual(command_with_modified_prefix, modified_prefix + " " + expected_cmd)

    def test_shutdown(self):
        """Test shutdown."""

        mock_logger = mock.MagicMock(name='LOG')
        mongodb_setup.LOG.warn = mock_logger
        self.mongo_node.shutdown_options = '{}'
        self.mongo_node.run_mongo_shell = mock.MagicMock(name='run_mongo_shell')
        self.mongo_node.run_mongo_shell.return_value = True
        self.assertTrue(self.mongo_node.shutdown(1))
        self.mongo_node.run_mongo_shell.assert_called_once_with(
            'db.getSiblingDB("admin").shutdownServer({})', max_time_ms=1)
        mock_logger.assert_not_called()

    def test_shutdown_options(self):
        """Test failed shutdown with options."""

        mock_logger = mock.MagicMock(name='LOG')
        mongodb_setup.LOG.warn = mock_logger
        self.mongo_node.run_mongo_shell = mock.MagicMock(name='run_mongo_shell')
        self.mongo_node.shutdown_options = 'options'
        self.mongo_node.run_mongo_shell.return_value = False
        self.assertFalse(self.mongo_node.shutdown(None))
        self.mongo_node.run_mongo_shell.assert_called_once_with(
            'db.getSiblingDB("admin").shutdownServer(options)', max_time_ms=None)
        mock_logger.assert_called_once_with(ANY_IN_STRING('did not shutdown'), mock.ANY, mock.ANY)

    def test_shutdown_exception(self):
        """Test shutdown."""

        mock_logger = mock.MagicMock(name='LOG')
        mongodb_setup.LOG.error = mock_logger
        self.mongo_node.run_mongo_shell = mock.MagicMock(name='run_mongo_shell')
        self.mongo_node.run_mongo_shell.side_effect = Exception()
        self.assertFalse(self.mongo_node.shutdown(None))
        mock_logger.assert_called_once_with(
            ANY_IN_STRING('Error shutting down MongoNode at'), mock.ANY, mock.ANY)

    def test_destroy(self):
        """Test destroy."""

        self.mongo_node.host.kill_mongo_procs = mock.MagicMock(name='kill_mongo_procs')
        self.mongo_node.host.run = mock.MagicMock(name='run')
        self.mongo_node.host.kill_mongo_procs.return_value = True
        self.assertTrue(self.mongo_node.destroy(1))
        calls = [mock.call(signal_number=15, max_time_ms=1), mock.call()]
        self.mongo_node.host.kill_mongo_procs.assert_has_calls(calls)
        self.mongo_node.host.run.assert_called_once_with(['rm', '-rf', 'data/dbs/mongod.lock'])

        self.mongo_node.host.kill_mongo_procs = mock.MagicMock(name='kill_mongo_procs')
        self.mongo_node.host.run = mock.MagicMock(name='run')
        self.mongo_node.host.kill_mongo_procs.return_value = False
        self.mongo_node.dbdir = None
        self.assertFalse(self.mongo_node.destroy(2))
        calls = [mock.call(signal_number=15, max_time_ms=2), mock.call()]
        self.mongo_node.host.kill_mongo_procs.assert_has_calls(calls)
        self.mongo_node.host.run.assert_not_called()

        self.mongo_node.host.kill_mongo_procs = mock.MagicMock(name='kill_mongo_procs')
        self.mongo_node.host.kill_mongo_procs.side_effect = [Exception(), True]
        self.mongo_node.host.run = mock.MagicMock(name='run')

        with self.assertRaises(Exception):
            self.mongo_node.destroy(2)
        calls = [mock.call(signal_number=15, max_time_ms=2), mock.call()]
        self.mongo_node.host.kill_mongo_procs.assert_has_calls(calls)


class TestReplSet(unittest.TestCase):
    """ReplSet tests"""

    def setUp(self):
        self.repl_set_opts = {
            'name': 'rs',
            'mongod': [mongodb_setup.copy_obj(MONGOD_OPTS),
                       mongodb_setup.copy_obj(MONGOD_OPTS)]
        }
        self.replset = mongodb_setup.ReplSet(self.repl_set_opts, config=DEFAULT_CONFIG)

    def test_shutdown(self):
        """Test shutdown."""
        with mock.patch('mongodb_setup.run_threads') as mock_run_threads, \
                mock.patch('mongodb_setup.partial') as mock_partial:
            mock_run_threads.return_value = [True]
            self.assertTrue(self.replset.shutdown(1))
            mock_partial.assert_has_calls([
                mock.call(self.replset.nodes[0].shutdown, 1),
                mock.call(self.replset.nodes[1].shutdown, 1)
            ])

        with mock.patch('mongodb_setup.run_threads') as mock_run_threads, \
                mock.patch('mongodb_setup.partial') as mock_partial:
            mock_run_threads.return_value = [True, False]
            self.assertFalse(self.replset.shutdown(2))
            mock_partial.assert_has_calls([mock.call(mock.ANY, 2), mock.call(mock.ANY, 2)])

    def test_destroy(self):
        """Test destroy."""
        with mock.patch('mongodb_setup.run_threads') as mock_run_threads, \
                mock.patch('mongodb_setup.partial') as mock_partial:
            mock_run_threads.return_value = [True]
            self.replset.destroy(1)
            mock_partial.assert_has_calls([
                mock.call(self.replset.nodes[0].destroy, 1),
                mock.call(self.replset.nodes[1].destroy, 1)
            ])

        with mock.patch('mongodb_setup.run_threads') as mock_run_threads, \
                mock.patch('mongodb_setup.partial') as mock_partial:
            mock_run_threads.return_value = [True, False]
            self.replset.destroy(2)
            mock_partial.assert_has_calls([mock.call(mock.ANY, 2), mock.call(mock.ANY, 2)])

    def test_highest_priority_node(self):
        """Test priority handling."""
        # pylint: disable=protected-access
        repl_set_opts = {
            'name':
                'rs',
            'mongod': [
                mongodb_setup.copy_obj(MONGOD_OPTS),
                mongodb_setup.copy_obj(MONGOD_OPTS),
                mongodb_setup.copy_obj(MONGOD_OPTS),
                mongodb_setup.copy_obj(MONGOD_OPTS)
            ]
        }

        # All default priorities
        replset = mongodb_setup.ReplSet(topology=repl_set_opts, config=DEFAULT_CONFIG)
        replset._set_explicit_priorities()
        self.assertEquals(replset.highest_priority_node(), replset.nodes[0])
        self.assertEquals(replset.rs_conf_members[0]['priority'], 2)
        self.assertEquals(replset.rs_conf_members[1]['priority'], 1)
        self.assertEquals(replset.rs_conf_members[2]['priority'], 1)
        self.assertEquals(replset.rs_conf_members[3]['priority'], 1)

        # Set one priority, others default
        repl_set_opts['mongod'][1]['rs_conf_member']['priority'] = 5
        replset = mongodb_setup.ReplSet(topology=repl_set_opts, config=DEFAULT_CONFIG)
        replset._set_explicit_priorities()
        self.assertEquals(replset.highest_priority_node(), replset.nodes[1])
        self.assertEquals(replset.rs_conf_members[0]['priority'], 2)
        self.assertEquals(replset.rs_conf_members[1]['priority'], 5)
        self.assertEquals(replset.rs_conf_members[2]['priority'], 1)
        self.assertEquals(replset.rs_conf_members[3]['priority'], 1)

        # Set all priorities explicitly in rs_conf_member
        repl_set_opts['mongod'][0]['rs_conf_member']['priority'] = 1
        repl_set_opts['mongod'][1]['rs_conf_member']['priority'] = 2
        repl_set_opts['mongod'][2]['rs_conf_member']['priority'] = 3
        repl_set_opts['mongod'][3]['rs_conf_member']['priority'] = 5
        replset = mongodb_setup.ReplSet(topology=repl_set_opts, config=DEFAULT_CONFIG)
        replset._set_explicit_priorities()
        self.assertEquals(replset.highest_priority_node(), replset.nodes[3])
        self.assertEquals(replset.rs_conf_members[0]['priority'], 1)
        self.assertEquals(replset.rs_conf_members[1]['priority'], 2)
        self.assertEquals(replset.rs_conf_members[2]['priority'], 3)
        self.assertEquals(replset.rs_conf_members[3]['priority'], 5)


class TestShardedCluster(unittest.TestCase):
    """ReplSet tests"""

    def setUp(self):
        self.cluster_opts = \
            {
                'disable_balancer': False,
                'configsvr_type': 'csrs',
                'mongos': [mongodb_setup.copy_obj(MONGOD_OPTS)],
                'configsvr': [mongodb_setup.copy_obj(MONGOD_OPTS)],
                'shard': [{'id': 'shard',
                           'cluster_type': 'replset',
                           'mongod': [mongodb_setup.copy_obj(MONGOD_OPTS),
                                      mongodb_setup.copy_obj(MONGOD_OPTS)]}]
            }
        self.cluster = mongodb_setup.ShardedCluster(self.cluster_opts, config=DEFAULT_CONFIG)

    def test_shutdown(self):
        """Test shutdown."""
        with mock.patch('mongodb_setup.run_threads') as mock_run_threads, \
                mock.patch('mongodb_setup.partial') as mock_partial:
            mock_run_threads.return_value = [True]
            self.assertTrue(self.cluster.shutdown(1))
            mock_partial.assert_has_calls([
                mock.call(self.cluster.shards[0].shutdown, 1),
                mock.call(self.cluster.config_svr.shutdown, 1),
                mock.call(self.cluster.mongoses[0].shutdown, 1),
            ])

        with mock.patch('mongodb_setup.run_threads') as mock_run_threads, \
                mock.patch('mongodb_setup.partial') as mock_partial:
            mock_run_threads.return_value = [True, False]
            self.assertFalse(self.cluster.shutdown(2))
            mock_partial.assert_has_calls([
                mock.call(mock.ANY, 2),
                mock.call(mock.ANY, 2),
                mock.call(mock.ANY, 2),
            ])

    def test_destroy(self):
        """Test destroy."""
        with mock.patch('mongodb_setup.run_threads') as mock_run_threads, \
                mock.patch('mongodb_setup.partial') as mock_partial:
            mock_run_threads.return_value = [True]
            self.cluster.config_svr.destroy = mock.MagicMock(name="config")
            self.cluster.destroy(1)
            mock_partial.assert_has_calls(
                [
                    mock.call(self.cluster.shards[0].destroy, 1),
                    mock.call(self.cluster.mongoses[0].destroy, 1),
                ],
                any_order=True)
            self.cluster.config_svr.destroy.assert_called_once_with(1)

        with mock.patch('mongodb_setup.run_threads') as mock_run_threads, \
                mock.patch('mongodb_setup.partial') as mock_partial:
            mock_run_threads.return_value = [True, False]
            self.cluster.config_svr.destroy = mock.MagicMock(name="config")
            self.cluster.destroy(2)
            mock_partial.assert_has_calls(
                [
                    mock.call(mock.ANY, 2),
                    mock.call(mock.ANY, 2),
                ], any_order=True)
            self.cluster.config_svr.destroy.assert_called_once_with(2)


class TestMongodbSetup(unittest.TestCase):
    """MongodbSetup tests"""

    def setUp(self):
        """Common options"""
        self.config = DEFAULT_CONFIG

    def test_timeouts(self):
        """Test shutdown / sigterm timeouts"""
        setup = mongodb_setup.MongodbSetup(self.config)
        self.assertEqual(setup.shutdown_ms, 540000)
        self.assertEqual(setup.sigterm_ms, 60000)

        self.config['mongodb_setup']['timeouts'] = {
            'shutdown_ms': 'shutdown',
            'sigterm_ms': 'sigterm'
        }
        setup = mongodb_setup.MongodbSetup(self.config)
        self.assertEqual(setup.shutdown_ms, 'shutdown')
        self.assertEqual(setup.sigterm_ms, 'sigterm')

    @mock.patch.object(common.host, 'Host', autospec=True)
    def start(self, host):
        """Starting ignores shutdown fails """
        setup = mongodb_setup.MongodbSetup(config=self.config)
        setup.host = host
        setup.downloader = mock.MagicMock()

        host.run = mock.MagicMock()
        mongodb_setup.MongoNode.wait_until_up = mock.MagicMock()
        setup.destroy = mock.MagicMock(name='destroy')
        setup.shutdown = mock.MagicMock(name='shutdown')
        setup.shutdown.return_value = True
        setup.downloader = mock.MagicMock()

        with mock.patch('mongodb_setup.run_threads') as mock_run_threads:
            mock_run_threads.return_value = [True]
            self.assertTrue(setup.restart())
            setup.destroy.assert_called_once_with(60000)
            setup.shutdown.assert_called_once_with(540000)
            setup.downloader.download_and_extract.assert_not_called()
            mock_run_threads.assert_called_once()

    # pylint: disable=protected-access
    def test_start(self):
        """ test start"""

        @mock.patch('mongodb_setup.common.host.run_host_commands')
        def _test_start(mock_run_host_commands, download_status=False, pre_cluster_start=False):
            test_config = copy.deepcopy(self.config)
            if pre_cluster_start:
                test_config['mongodb_setup']['pre_cluster_start'] = [{
                    'on_all_hosts': {
                        'retrieve_files': [{
                            'source': 'foo',
                            'target': 'bar'
                        }]
                    }
                }]

            setup = mongodb_setup.MongodbSetup(config=test_config)
            setup.downloader.download_and_extract = mock.MagicMock(name='downloader')

            setup._start = mock.MagicMock(name='_start')
            setup._start.return_value = "start clusters"
            setup.destroy = mock.MagicMock(name='destroy')
            # shutdown should never be called in this path
            setup.shutdown = mock.MagicMock(name='shutdown')
            setup.downloader.download_and_extract.return_value = download_status

            if not download_status:
                self.assertEquals(setup.start(), False)
                setup._start.assert_not_called()
            else:
                self.assertEquals(setup.start(), "start clusters")
                setup._start.assert_called_once()

            if pre_cluster_start:
                mock_run_host_commands.assert_called_with(
                    test_config['mongodb_setup']['pre_cluster_start'], test_config,
                    "pre_cluster_start")
            else:
                mock_run_host_commands.assert_not_called()

            setup.destroy.assert_called_once_with(60000)
            setup.shutdown.assert_not_called()
            setup.downloader.download_and_extract.assert_called_once()

        # Pylint is unable to handle the idea that @patch decorator is filling in a
        # parameter. Disabling locally.

        # pylint: disable=no-value-for-parameter
        _test_start()
        # The following case will not call run_host_commands because setup will exit before
        # _test_start(download_status=True)
        _test_start(download_status=True, pre_cluster_start=True)
        _test_start(download_status=True, pre_cluster_start=False)
        # pylint: enable=no-value-for-parameter

    def test_restart(self):
        """ test start"""

        def _test_restart(shutdown=True):
            setup = mongodb_setup.MongodbSetup(config=self.config)

            setup._start = mock.MagicMock(name='_start')
            setup._start.return_value = "start clusters"

            setup.destroy = mock.MagicMock(name='destroy')
            setup.shutdown = mock.MagicMock(name='shutdown')
            setup.shutdown.return_value = shutdown

            if not shutdown:
                self.assertEquals(setup.restart(), False)
                setup._start.assert_not_called()
            else:
                self.assertEquals(setup.restart(), "start clusters")
                setup._start.assert_called_once_with(
                    is_restart=True, restart_clean_db_dir=None, restart_clean_logs=None)
            setup.destroy.assert_called_once_with(60000)
            setup.shutdown.assert_called_once_with(540000)

        _test_restart()
        _test_restart(shutdown=False)

    def test__start(self):
        """Restarting fails when shutdown fails"""

        def _test__start(run_threads, success=True):

            setup = mongodb_setup.MongodbSetup(config=self.config)
            setup.downloader = mock.MagicMock()
            setup.downloader.download_and_extract.return_value = False
            mongodb_setup.MongoNode.wait_until_up = mock.MagicMock()
            setup.destroy = mock.MagicMock(name='destroy')
            setup.shutdown = mock.MagicMock(name='shutdown')
            setup.shutdown.return_value = False

            with mock.patch('mongodb_setup.run_threads') as mock_run_threads,\
                 mock.patch('mongodb_setup.partial') as mock_partial:
                mock_run_threads.return_value = run_threads
                mock_partial.return_value = 'threads'

                self.assertEquals(setup._start(), success)
                calls = [
                    mock.call(
                        setup.start_cluster,
                        cluster=setup.clusters[0],
                        is_restart=False,
                        restart_clean_db_dir=None,
                        restart_clean_logs=None)
                ]
                mock_partial.assert_has_calls(calls)
                setup.destroy.assert_not_called()
                if success:
                    setup.shutdown.assert_not_called()
                else:
                    setup.shutdown.assert_called_once_with(540000)
                setup.downloader.download_and_extract.assert_not_called()
                mock_run_threads.assert_called_once_with(['threads'], daemon=True)

        _test__start([True])
        _test__start([True, True])
        _test__start([True, False], success=False)

    def test_shutdown(self):
        """Test MongoDbSetup.shutdown """

        setup = mongodb_setup.MongodbSetup(config=self.config)
        mock_cluster1 = mock.MagicMock(name='cluster1')
        mock_cluster2 = mock.MagicMock(name='cluster2')
        setup.clusters = [mock_cluster1, mock_cluster2]
        with mock.patch('mongodb_setup.run_threads') as mock_run_threads, \
                mock.patch('mongodb_setup.partial') as mock_partial:

            mock_run_threads.return_value = [True]
            self.assertTrue(setup.shutdown(1))
            mock_partial.assert_has_calls(
                [mock.call(mock_cluster1.shutdown, 1),
                 mock.call(mock_cluster2.shutdown, 1)])

    def test_destroy(self):
        """Test MongoDbSetup.destroy"""

        setup = mongodb_setup.MongodbSetup(config=self.config)
        mock_cluster1 = mock.MagicMock(name='cluster1')
        mock_cluster2 = mock.MagicMock(name='cluster2')
        setup.clusters = [mock_cluster1, mock_cluster2]
        with mock.patch('mongodb_setup.run_threads') as mock_run_threads, \
                mock.patch('mongodb_setup.partial') as mock_partial:

            mock_run_threads.return_value = [True]
            self.assertTrue(setup.destroy(1))
            mock_partial.assert_has_calls(
                [mock.call(mock_cluster1.destroy, 1),
                 mock.call(mock_cluster2.destroy, 1)])


if __name__ == '__main__':
    unittest.main()
