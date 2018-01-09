#!/usr/bin/env python
"""Tests for the mongodb_setup module"""
import os
import os.path
import unittest

import mock

import mongodb_setup
import common.host

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
                        '*.log', 'core.*', 'db/diagnostic.data/*', 'diagnostic.data', 'db',
                        '/media/ephemeral1/journal'
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

    # pylint: disable=unused-argument
    @mock.patch('mongodb_setup.DownloadMongodb')
    def test_ssh_key(self, mock_downloader):
        """Test ~/.ssh/user_aws_key.pem"""
        mongodb_setup.MongodbSetup(self.config)
        ssh_key_file = self.config['infrastructure_provisioning']['tfvars']['ssh_key_file']
        expected_ssh_key_file = os.path.expanduser(ssh_key_file)
        self.assertEquals(mongodb_setup.MongoNode.ssh_key_file, expected_ssh_key_file)
        self.assertEquals(mongodb_setup.MongoNode.ssh_user, 'ec2-user')

    @mock.patch.object(common.host, 'Host', autospec=True)
    def test_restart_does_not_download(self, host):
        """Restarting doesn't re-download"""
        setup = mongodb_setup.MongodbSetup(config=self.config)
        setup.host = host
        setup.downloader = mock.MagicMock()

        host.run = mock.MagicMock()
        mongodb_setup.MongoNode.wait_until_up = mock.MagicMock()

        out = setup.restart()
        self.assertIs(out, True)

        setup.downloader.assert_not_called()


if __name__ == '__main__':
    unittest.main()
