"""Tests for bin/common/host.py"""
#pylint: disable=unused-argument, no-self-use, protected-access

import collections
import os
import sys
import stat
import unittest
import paramiko

from mock import patch, Mock, mock

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/common")

from config import ConfigDict
import host

FakeStat = collections.namedtuple('FakeStat', 'st_mode')


class HostTestCase(unittest.TestCase):
    """ Unit Test for Host library """

    def setUp(self):
        """ Init a ConfigDict object and load the configuration files from docs/config-specs/ """
        self.old_dir = os.getcwd()  # Save the old path to restore
        # Note that this chdir only works without breaking relative imports
        # because it's at the same directory depth
        os.chdir(os.path.dirname(os.path.abspath(__file__)) + '/../../docs/config-specs/')
        self.config = ConfigDict('mongodb_setup')
        self.config.load()

    def tearDown(self):
        """ Restore working directory """
        os.chdir(self.old_dir)

    def test_extract_hosts(self):
        """ Test extract hosts using config info """
        mongods = [host.HostInfo('53.1.1.{}'.format(i + 1), "mongod", i) for i in range(0, 9)]
        configsvrs = [
            host.HostInfo('53.1.1.{}'.format(i + 51), "configsvr", i) for i in range(0, 3)
        ]
        mongos = [host.HostInfo('53.1.1.{}'.format(i + 100), "mongos", i) for i in range(0, 3)]
        workload_clients = [host.HostInfo('53.1.1.101', "workload_client", 0)]
        localhost = [host.HostInfo('localhost', 'localhost', 0)]

        self.assertEqual(host.extract_hosts('localhost', self.config), localhost)
        self.assertEqual(host.extract_hosts('workload_client', self.config), workload_clients)
        self.assertEqual(host.extract_hosts('mongod', self.config), mongods)
        self.assertEqual(host.extract_hosts('mongos', self.config), mongos)
        self.assertEqual(host.extract_hosts('configsvr', self.config), configsvrs)
        self.assertEqual(
            host.extract_hosts('all_servers', self.config), mongods + mongos + configsvrs)
        self.assertEqual(
            host.extract_hosts('all_hosts', self.config),
            mongods + mongos + configsvrs + workload_clients)

    @patch('paramiko.SSHClient')
    def test_alias(self, mock_ssh):
        """ Test alias """

        remote_host = host.RemoteHost("host", "user", "pem_file")
        self.assertEqual(remote_host.alias, "host")

        remote_host.alias = ""
        self.assertEqual(remote_host.alias, "host")

        remote_host.alias = None
        self.assertEqual(remote_host.alias, "host")

        remote_host.alias = "alias"
        self.assertEqual(remote_host.alias, "alias")

    @patch('paramiko.SSHClient')
    def test_make_host(self, mock_ssh):
        """ Test make host """

        host_info = host.HostInfo('53.1.1.1', "mongod", 0)
        mongod = host.make_host(host_info, "ssh_user", "ssh_key_file")
        self.assertEqual(mongod.alias, 'mongod.0', "alias not set as expected")

        host_info = host.HostInfo('53.0.0.1', "mongos", 1)
        mongos = host.make_host(host_info, "ssh_user", "ssh_key_file")
        self.assertEqual(mongos.alias, 'mongos.1', "alias not set as expected")

        for ip_or_name in ['localhost', '127.0.0.1', '0.0.0.0']:
            host_info = host.HostInfo(ip_or_name, "localhost", 0)
            localhost = host.make_host(host_info, "ssh_user", "ssh_key_file")
            self.assertEqual(localhost.alias, 'localhost.0', "alias not set as expected")

    @patch('paramiko.SSHClient')
    def test_run_command_map(self, mock_ssh):
        """ Test run command map retrieve_files """

        mock_retrieve_file = Mock()
        host.RemoteHost.retrieve_path = mock_retrieve_file

        command = {"retrieve_files": {"remote_path": "mongos.log"}}
        mongod = host.RemoteHost("host", "user", "pem_file")
        host._run_command_map(mongod, command)
        mock_retrieve_file.assert_any_call("reports/host/mongos.log", "remote_path")

        mock_retrieve_file = Mock()
        host.RemoteHost.retrieve_path = mock_retrieve_file

        command = {"retrieve_files": {"remote_path": "local_path"}}
        mongod = host.RemoteHost("host", "user", "pem_file")
        host._run_command_map(mongod, command)
        mock_retrieve_file.assert_any_call("reports/host/local_path", "remote_path")

        mock_retrieve_file = Mock()
        host.RemoteHost.retrieve_path = mock_retrieve_file

        mongod.alias = "mongod.0"
        host._run_command_map(mongod, command)
        mock_retrieve_file.assert_any_call("reports/mongod.0/local_path", "remote_path")

        mock_retrieve_file = Mock()
        host.RemoteHost.retrieve_path = mock_retrieve_file

        command = {"retrieve_files": {"remote_path": "./local_path"}}
        mongod.alias = "mongos.0"
        host._run_command_map(mongod, command)
        mock_retrieve_file.assert_any_call("reports/mongos.0/local_path", "remote_path")

        mock_retrieve_file = Mock()
        host.RemoteHost.retrieve_path = mock_retrieve_file

        # deliberate jail break for workload client backwards compatibility
        command = {
            "retrieve_files": {
                "workloads/workload_timestamps.csv": "../workloads_timestamps.csv"
            }
        }
        mongod.alias = "workload_client.0"
        host._run_command_map(mongod, command)
        mock_retrieve_file.assert_any_call("reports/workload_client.0/../workloads_timestamps.csv",
                                           "workloads/workload_timestamps.csv")

    @patch('paramiko.SSHClient')
    def test_remote_host_isdir(self, mock_ssh):
        """ Test run command map retrieve_files """

        remote = host.RemoteHost('53.1.1.1', "ssh_user", "ssh_key_file")
        remote.ftp.stat.return_value = FakeStat(st_mode=stat.S_IFDIR)
        isdir = remote.remote_isdir('/true')

        self.assertTrue(isdir, "expected true")
        remote.ftp.stat.assert_called_with('/true')

        remote.ftp.stat.return_value = FakeStat(st_mode=stat.S_IFLNK)
        isdir = remote.remote_isdir('/false')

        self.assertFalse(isdir, "expected False")
        remote.ftp.stat.assert_called_with('/false')

        remote.ftp = mock_ssh
        mock_ssh.stat.side_effect = os.error(2, 'No such file or directory:')
        isdir = remote.remote_isdir('/exception')

        self.assertFalse(isdir, "expected False")
        remote.ftp.stat.assert_called_with('/exception')

    @patch('paramiko.SSHClient')
    def test_exists_os_error(self, mock_ssh):
        """ Test run RemoteHost.exists """

        remote = host.RemoteHost('53.1.1.1', "ssh_user", "ssh_key_file")
        exists = remote.remote_exists('true_path')

        self.assertTrue(exists, "expected true")
        remote.ftp.stat.assert_called_with('true_path')

        remote.ftp = mock_ssh
        mock_ssh.stat.side_effect = os.error(2, 'No such file or directory:')
        exists = remote.remote_exists('os_exception_path')

        self.assertFalse(exists, "expected False")
        remote.ftp.stat.assert_called_with('os_exception_path')

    @patch('paramiko.SSHClient')
    def test_exists_io_error(self, mock_ssh):
        """ Test run RemoteHost.exists """

        remote = host.RemoteHost('53.1.1.1', "ssh_user", "ssh_key_file")
        exists = remote.remote_exists('true_path')

        self.assertTrue(exists, "expected true")
        remote.ftp.stat.assert_called_with('true_path')

        remote.ftp = mock_ssh
        mock_ssh.stat.side_effect = IOError('IOError')
        exists = remote.remote_exists('io_exception_path')

        self.assertFalse(exists, "expected False")
        remote.ftp.stat.assert_called_with('io_exception_path')

    @patch('paramiko.SSHClient')
    def test_exists_paramiko_error(self, mock_ssh):
        """ Test run RemoteHost.exists """

        remote = host.RemoteHost('53.1.1.1', "ssh_user", "ssh_key_file")
        exists = remote.remote_exists('true_path')

        self.assertTrue(exists, "expected true")
        remote.ftp.stat.assert_called_with('true_path')

        remote.ftp = mock_ssh
        mock_ssh.stat.side_effect = paramiko.SFTPError('paramiko.SFTPError')
        exists = remote.remote_exists('paramiko_exception_path')

        self.assertFalse(exists, "expected False")
        remote.ftp.stat.assert_called_with('paramiko_exception_path')

    @patch('paramiko.SSHClient')
    @patch('os.makedirs')
    @patch('os.path.exists')
    def test__retrieve_file(self, mock_exists, mock_makedirs, mock_ssh):
        """ Test run RemoteHost.exists """

        mock_exists.return_value = True
        remote = host.RemoteHost('53.1.1.1', "ssh_user", "ssh_key_file")
        remote._retrieve_file('reports/local_file', 'remote_file')

        remote.ftp.get.assert_called_with('remote_file', 'reports/local_file')
        mock_makedirs.assert_not_called()

        mock_exists.return_value = True
        remote = host.RemoteHost('53.1.1.1', "ssh_user", "ssh_key_file")
        remote._retrieve_file('reports/mongod.0/local_file', 'remote_file')

        remote.ftp.get.assert_called_with('remote_file', 'reports/mongod.0/local_file')
        mock_makedirs.assert_not_called()

        mock_exists.return_value = True
        remote = host.RemoteHost('53.1.1.1', "ssh_user", "ssh_key_file")
        remote._retrieve_file('reports/../local_file', 'remote_file')

        remote.ftp.get.assert_called_with('remote_file', 'local_file')
        mock_makedirs.assert_not_called()

        with patch('os.makedirs') as mock_makedirs:
            mock_exists.return_value = False
            remote = host.RemoteHost('53.1.1.1', "ssh_user", "ssh_key_file")
            remote._retrieve_file('reports/local_file', 'remote_file')

            remote.ftp.get.assert_called_with('remote_file', 'reports/local_file')
            mock_makedirs.assert_called_with('reports')

    @patch('paramiko.SSHClient')
    def test_retrieve_file_for_files(self, mock_ssh):
        """ Test run RemoteHost.exists """

        # remote path does not exist
        remote = host.RemoteHost('53.1.1.1', "ssh_user", "ssh_key_file")
        remote.remote_exists = Mock()
        remote.remote_isdir = Mock()
        remote._retrieve_file = Mock()
        remote.ftp.listdir = Mock()

        remote.remote_exists.return_value = False
        remote.retrieve_path('reports/local_file', 'remote_file')

        remote.remote_isdir.assert_not_called()

        # remote path is a single file
        remote.remote_exists.reset_mock()
        remote.remote_isdir.reset_mock()
        remote._retrieve_file.reset_mock()
        remote.ftp.listdir.reset_mock()

        remote.remote_exists.return_value = True
        remote.remote_isdir.return_value = False
        remote.retrieve_path('reports/local_file', 'remote_file')
        remote._retrieve_file.assert_called_with('reports/local_file', 'remote_file')

        # remote path is a directory containing a single file
        remote.remote_exists.reset_mock()
        remote.remote_isdir.reset_mock()
        remote._retrieve_file.reset_mock()
        remote.ftp.listdir.reset_mock()

        remote.remote_exists.return_value = True
        isdir_map = {'remote_dir': True}
        remote.remote_isdir.side_effect = lambda name: isdir_map.get(name, False)
        remote.ftp.listdir.return_value = ['mongod.log']

        remote.retrieve_path('reports/local_dir', 'remote_dir')

        remote.ftp.listdir.assert_called_with('remote_dir')
        remote._retrieve_file.assert_called_with('reports/local_dir/mongod.log',
                                                 'remote_dir/mongod.log')

        # remote path is a directory, with multiple files
        remote.remote_exists.reset_mock()
        remote.remote_isdir.reset_mock()
        remote._retrieve_file.reset_mock()
        remote.ftp.listdir.reset_mock()

        remote.remote_exists.return_value = True
        isdir_map = {'remote_dir': True}
        remote.remote_isdir.side_effect = lambda name: isdir_map.get(name, False)
        remote.ftp.listdir.return_value = [
            'mongod.log', 'metrics.2017-04-27T09-14-33Z-00000', 'metrics.interim'
        ]

        remote.retrieve_path('reports/local_dir', 'remote_dir')

        remote.ftp.listdir.assert_called_with('remote_dir')
        self.assertTrue(remote._retrieve_file.mock_calls == [
            mock.call('reports/local_dir/mongod.log', 'remote_dir/mongod.log'),
            mock.call('reports/local_dir/metrics.2017-04-27T09-14-33Z-00000',
                      'remote_dir/metrics.2017-04-27T09-14-33Z-00000'),
            mock.call('reports/local_dir/metrics.interim', 'remote_dir/metrics.interim')
        ])

    @patch('paramiko.SSHClient')
    def test_retrieve_file_with_dirs(self, mock_ssh):
        """ Test run RemoteHost.exists """

        remote = host.RemoteHost('53.1.1.1', "ssh_user", "ssh_key_file")
        remote.remote_exists = Mock()
        remote.remote_isdir = Mock()
        remote._retrieve_file = Mock()
        remote.ftp.listdir = Mock()

        # remote path is a directory, with 1 directory with a single empty dir
        remote.remote_exists.reset_mock()
        remote.remote_isdir.reset_mock()
        remote._retrieve_file.reset_mock()
        remote.ftp.listdir.reset_mock()

        remote.remote_exists.return_value = True
        isdir_map = {'remote_dir': True, 'remote_dir/data': True}
        remote.remote_isdir.side_effect = lambda name: isdir_map.get(name, False)

        listdir_map = {'remote_dir': ['data']}
        remote.ftp.listdir.side_effect = lambda name: listdir_map.get(name, [])

        remote.retrieve_path('reports/local_dir', 'remote_dir')
        self.assertTrue(
            remote.ftp.listdir.mock_calls ==
            [mock.call('remote_dir'), mock.call('remote_dir/data')])
        # remote.ftp.listdir.assert_called_with('remote_dir')
        remote._retrieve_file.assert_not_called()

        # remote path is a directory, with 1 directory (with a single file)
        remote.remote_exists.reset_mock()
        remote.remote_isdir.reset_mock()
        remote._retrieve_file.reset_mock()
        remote.ftp.listdir.reset_mock()

        remote.remote_exists.return_value = True
        isdir_map = {'remote_dir': True, 'remote_dir/data': True}
        remote.remote_isdir.side_effect = lambda name: isdir_map.get(name, False)

        listdir_map = {'remote_dir': ['data'], 'remote_dir/data': ['metrics.interim']}
        remote.ftp.listdir.side_effect = lambda name: listdir_map.get(name, [])

        remote.retrieve_path('reports/local_dir', 'remote_dir')
        self.assertTrue(
            remote.ftp.listdir.mock_calls ==
            [mock.call('remote_dir'), mock.call('remote_dir/data')])
        # remote.ftp.listdir.assert_called_with('remote_dir')
        remote._retrieve_file.assert_called_with('reports/local_dir/data/metrics.interim',
                                                 'remote_dir/data/metrics.interim')

        # remote path is a directory, with multiple files
        remote.remote_exists.reset_mock()
        remote.remote_isdir.reset_mock()
        remote._retrieve_file.reset_mock()
        remote.ftp.listdir.reset_mock()

        remote.remote_exists.return_value = True
        isdir_map = {'remote_dir': True}
        remote.remote_isdir.side_effect = lambda name: isdir_map.get(name, False)

        listdir_map = {'remote_dir': ['data', 'logs']}
        remote.ftp.listdir.side_effect = lambda name: listdir_map.get(name, [])

        remote.retrieve_path('reports/local_dir', 'remote_dir')
        remote.ftp.listdir.assert_called_with('remote_dir')
        self.assertTrue(remote._retrieve_file.mock_calls == [
            mock.call('reports/local_dir/data', 'remote_dir/data'),
            mock.call('reports/local_dir/logs', 'remote_dir/logs')
        ])

    @patch('paramiko.SSHClient')
    def test_retrieve_files_and_dirs(self, mock_ssh):
        """ Test run RemoteHost.exists """

        remote = host.RemoteHost('53.1.1.1', "ssh_user", "ssh_key_file")
        remote.remote_exists = Mock()
        remote.remote_isdir = Mock()
        remote._retrieve_file = Mock()
        remote.ftp.listdir = Mock()

        # remote path is a directory, with files and directories
        remote.remote_exists.reset_mock()
        remote.remote_isdir.reset_mock()
        remote._retrieve_file.reset_mock()
        remote.ftp.listdir.reset_mock()

        remote.remote_exists.return_value = True

        isdir_map = {
            'remote_dir': True,
            'remote_dir/data': True,
            'remote_dir/empty': True,
            'remote_dir/logs': True
        }

        remote.remote_isdir.side_effect = lambda name: isdir_map.get(name, False)

        listdir_map = {
            'remote_dir': ['data', 'empty', 'file', 'logs'],
            'remote_dir/data': ['metrics.interim', 'metrics.2017-04-27T09-14-33Z-00000'],
            'remote_dir/logs': ['mongod.log']
        }
        remote.ftp.listdir.side_effect = lambda name: listdir_map.get(name, [])

        remote.retrieve_path('reports/local_dir', 'remote_dir')

        # note empty is not here so it was not called
        self.assertTrue(remote._retrieve_file.mock_calls == [
            mock.call('reports/local_dir/data/metrics.interim', 'remote_dir/data/metrics.interim'),
            mock.call('reports/local_dir/data/metrics.2017-04-27T09-14-33Z-00000',
                      'remote_dir/data/metrics.2017-04-27T09-14-33Z-00000'),
            mock.call('reports/local_dir/file', 'remote_dir/file'),
            mock.call('reports/local_dir/logs/mongod.log', 'remote_dir/logs/mongod.log')
        ])

    @patch("host.RemoteHost.exec_command")
    @patch("host.RemoteHost.create_file")
    @patch('paramiko.SSHClient')
    def test_exec_mongo_command(self, mock_ssh, mock_create_file, mock_exec_command):
        """ Test run RemoteHost.exec_mongo_command """
        mock_exec_command.return_value = 0
        test_file = 'test_file'
        test_user = 'test_user'
        test_pem_file = 'test_pem_file'
        test_host = 'test_host'
        test_script = 'test_script'
        test_connection_string = 'test_connection_string'
        test_argv = ['bin/mongo', '--verbose', test_connection_string, test_file]
        remote_host = host.RemoteHost(test_host, test_user, test_pem_file)
        status_code = remote_host.exec_mongo_command(test_script, test_file, test_connection_string)
        self.assertTrue(status_code == 0)
        mock_create_file.assert_called_with(test_file, test_script)
        mock_exec_command.assert_called_with(test_argv)

    @patch('paramiko.SSHClient')
    def test_run(self, mock_ssh):
        """Test RemoteHost.run"""
        ssh_instance = mock_ssh.return_value
        stdin = Mock()
        stdout = Mock()
        stderr = Mock()
        stdout.channel.recv_exit_status.return_value = 0
        stdout.readlines.return_value = ["mock cow: mu"]
        stderr.readlines.return_value = []
        ssh_instance.exec_command.return_value = [stdin, stdout, stderr]

        remote_host = host.RemoteHost('test_host', 'test_user', 'test_pem_file')
        # Test a command as string
        self.assertTrue(remote_host.run('cowsay Hello World'))
        # Test a command as list
        self.assertTrue(remote_host.run(['cowsay', 'Hello', 'List']))
        # Test a batch of commands
        batch = [['cowsay', 'Hello', 'One'], ['cowsay', 'Hello', 'Two']]
        self.assertTrue(remote_host.run(batch))
        # Test empty string and list
        with self.assertRaises(ValueError):
            self.assertTrue(remote_host.run(''))
        with self.assertRaises(ValueError):
            self.assertTrue(remote_host.run([]))
        # Anything else should fail
        with self.assertRaises(ValueError):
            remote_host.run(None)
        with self.assertRaises(ValueError):
            remote_host.run(0)

    @patch('paramiko.SSHClient')
    def test_exec_command(self, mock_ssh):
        """Test RemoteHost.exec_command"""
        # test_run() already tests exec_command too, but we test some incorrect input here
        remote_host = host.RemoteHost('test_host', 'test_user', 'test_pem_file')
        with self.assertRaises(ValueError):
            remote_host.exec_command(None)
        with self.assertRaises(ValueError):
            remote_host.exec_command(0)


if __name__ == '__main__':
    unittest.main()
