# pylint: disable=too-many-lines
# pylint: disable=unused-argument, no-self-use, protected-access, wrong-import-position
# pylint: disable=invalid-name
# pylint: disable=wrong-import-order
"""Tests for bin/common/host.py"""

import collections
from datetime import datetime
import os
import shutil
import socket
import sys
import stat
import time
import unittest
from StringIO import StringIO

import paramiko

from mock import patch, Mock, mock, MagicMock, call, ANY

import common.utils

from bin.common.host import make_host_runner, never_timeout, check_timed_out, create_timer, \
    _stream
from bin.common.log import TeeStream
from tests.any_in_string import ANY_IN_STRING

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/common")

from config import ConfigDict
import host

FakeStat = collections.namedtuple('FakeStat', 'st_mode')

# Useful absolute directory paths.
FIXTURE_DIR_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "unittest-files")


def fixture_file_path(file_path):
    """Return the absolute path of a file at `file_path` inside the fixture files directory."""

    return os.path.join(FIXTURE_DIR_PATH, file_path)


def sleepy_streamer(sleep_time_sec, outval):
    """
    :param sleep_time_sec: how long in seconds to sleep
    :param outval: forced return value
    :return: a function that sleeps for `sleep_time_sec` seconds and returns `outval`
    """

    # pylint: disable=missing-docstring
    def out(io1, io2):
        time.sleep(sleep_time_sec)
        return outval

    return out


# pylint: disable=too-many-public-methods
class HostTestCase(unittest.TestCase):
    """ Unit Test for Host library """

    def _delete_fixtures(self):
        """ delete fixture path and set filename attribute """
        local_host_path = fixture_file_path('fixtures')
        self.filename = os.path.join(local_host_path, 'file')
        shutil.rmtree(os.path.dirname(self.filename), ignore_errors=True)

    def setUp(self):
        """ Init a ConfigDict object and load the configuration files from docs/config-specs/ """
        self.old_dir = os.getcwd()  # Save the old path to restore
        # Note that this chdir only works without breaking relative imports
        # because it's at the same directory depth
        os.chdir(os.path.dirname(os.path.abspath(__file__)) + '/../../docs/config-specs/')
        self.config = ConfigDict('mongodb_setup')
        self.config.load()

        self._delete_fixtures()

    def tearDown(self):
        """ Restore working directory """
        os.chdir(self.old_dir)

        self._delete_fixtures()

    def test_never_timeout(self):
        """ test never_timeout"""
        self.assertFalse(never_timeout())
        self.assertFalse(never_timeout())

    def test_check_timed_out(self):
        """ test check_timed_out"""
        start = datetime.now()
        self.assertFalse(check_timed_out(start, 50))
        time.sleep(51 / 1000.0)
        self.assertTrue(check_timed_out(start, 50))

    def test_create_timer(self):
        """ test create_timer """
        start = datetime.now()
        self.assertEquals(create_timer(start, None), never_timeout)
        with patch('bin.common.host.partial') as mock_partial:
            self.assertTrue(create_timer(start, 50))
            mock_partial.assert_called_once_with(check_timed_out, start, 50)

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

    def test__stream(self):
        """ Test _stream, I wouldn't normally test an internal method, but it consumes
         an exception and it can then be stubbed or mocked later"""

        source = StringIO('source')
        destination = MagicMock(name="destination")
        source.next = MagicMock(name="in")
        source.next.side_effect = socket.timeout('args')
        any_lines = _stream(source, destination)
        self.assertEquals(False, any_lines)
        destination.write.assert_not_called()

        destination = MagicMock(name="destination")
        source.next = MagicMock(name="in")
        source.next.side_effect = ['first', 'second', socket.timeout('args'), 'third']
        any_lines = _stream(source, destination)
        self.assertEquals(True, any_lines)

        calls = [
            call('first'),
            call('second'),
        ]

        destination.write.assert_has_calls(calls)

    def test_kill_remote_procs(self):
        """ Test kill_remote_procs """

        local_host = host.LocalHost()
        local_host.run = MagicMock(name="run")
        local_host.run.return_value = False
        self.assertTrue(local_host.kill_remote_procs('mongo'))

        calls = [
            call(['pkill', '-9', 'mongo']),
            call(['pgrep', 'mongo']),
        ]

        local_host.run.assert_has_calls(calls)

        with patch('host.create_timer') as mock_create_watchdog:

            local_host.run = MagicMock(name="run")
            local_host.run.return_value = False
            local_host.kill_remote_procs('mongo', max_time_ms=None)
            mock_create_watchdog.assert_called_once_with(ANY, None)

        with patch('host.create_timer') as mock_create_watchdog:

            local_host.run = MagicMock(name="run")
            local_host.run.return_value = False
            local_host.kill_remote_procs('mongo', max_time_ms=0, delay_ms=99)
            mock_create_watchdog.assert_called_once_with(ANY, 99)

        with patch('host.create_timer') as mock_create_watchdog:
            local_host = host.LocalHost()
            local_host.run = MagicMock(name="run")
            local_host.run.return_value = True

            mock_is_timed_out = MagicMock(name="is_timed_out")
            mock_create_watchdog.return_value = mock_is_timed_out
            mock_is_timed_out.side_effect = [False, True]
            self.assertFalse(local_host.kill_remote_procs('mongo', delay_ms=1))

        local_host = host.LocalHost()
        local_host.run = MagicMock(name="run")
        local_host.run.side_effect = [False, True, False, False]
        self.assertTrue(local_host.kill_remote_procs('mongo', signal_number=15, delay_ms=1))

        calls = [
            call(['pkill', '-15', 'mongo']),
            call(['pgrep', 'mongo']),
            call(['pkill', '-15', 'mongo']),
            call(['pgrep', 'mongo']),
        ]

        local_host.run.assert_has_calls(calls)
        # mock_sleep.assert_not_called()

    def test_kill_mongo_procs(self):
        """ Test kill_mongo_procs """
        local_host = host.LocalHost()
        local_host.kill_remote_procs = MagicMock(name="kill_remote_procs")
        local_host.kill_remote_procs.return_value = True
        self.assertTrue(local_host.kill_mongo_procs())
        local_host.kill_remote_procs.assert_called_once_with('mongo', 9, max_time_ms=30000)

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

    def test_run_host_commands(self):
        """Test 2-commands host.run_host_commands invocation"""
        with patch('host.RemoteHost') as mongod:
            commands = [
                {
                    'on_workload_client': {
                        'upload_files': [{
                            'source': 'src1',
                            'target': 'dest1'
                        }]
                    }
                },
                {
                    'on_workload_client': {
                        'upload_files': [{
                            'source': 'src2',
                            'target': 'dest2'
                        }]
                    }
                },
            ]
            host.run_host_commands(commands, self.config, "test_id")
            assert mongod.call_count == 2

    def test_run_host_command_map(self):
        """ Test run command map not known """

        with self.assertRaises(UserWarning):
            with patch('host.RemoteHost') as mongod:
                command = {"garbage": {"remote_path": "mongos.log"}}
                host._run_host_command_map(mongod, command, "test_id")

    def test_upload_repo_files(self):
        """ Test run command map upload_repo_files """
        root = common.utils.get_dsi_path() + os.sep

        # test upload_repo_files
        with patch('host.RemoteHost') as mongod:
            command = {"upload_repo_files": [{"target": "remote_path", "source": "mongos.log"}]}
            host._run_host_command_map(mongod, command, "test_id")
            mongod.upload_file.assert_called_once_with(root + "mongos.log", "remote_path")

        with patch('host.RemoteHost') as mongod:
            command = {
                "upload_repo_files": [{
                    "target": "remote_path",
                    "source": "mongos.log"
                }, {
                    "target": "to",
                    "source": "from"
                }]
            }
            host._run_host_command_map(mongod, command, "test_id")
            calls = [
                mock.call(root + "mongos.log", "remote_path"),
                mock.call(root + "from", "to"),
            ]
            mongod.upload_file.assert_has_calls(calls, any_order=True)

    @patch('host._connected_ssh')
    def test_upload_files_dir(self, mock_connected_ssh):
        """We can upload directories of files"""

        ssh = mock.MagicMock(name='ssh')
        ftp = mock.MagicMock(name='ftp')
        channel = mock.MagicMock(name='channel')
        ssh.exec_command.return_value = channel, channel, channel

        mock_connected_ssh.return_value = (ssh, ftp)

        remote = host.RemoteHost(host=None, user=None, pem_file=None)

        local_path = os.path.abspath(os.path.dirname(__file__))
        remote_path = '/foo/bar'

        remote.upload_file(local_path, remote_path)

        ssh.exec_command.assert_has_calls(
            [
                call('mkdir -p /foo/bar', get_pty=False),
                call('tar xf /foo/bar.tar -C /foo/bar', get_pty=False),
                call('rm /foo/bar.tar', get_pty=False)
            ],
            any_order=False)

        ftp.assert_has_calls(
            [call.put(ANY, '/foo/bar.tar'),
             call.chmod('/foo/bar.tar', ANY)], any_order=False)

    @patch('host._connected_ssh')
    def test_upload_single_file(self, mock_connected_ssh):
        """We can upload a single file"""
        ssh = mock.MagicMock(name='ssh')
        ftp = mock.MagicMock(name='ftp')
        mock_connected_ssh.return_value = (ssh, ftp)

        remote = host.RemoteHost(host=None, user=None, pem_file=None)

        local_path = os.path.abspath(__file__)
        remote_path = '/foo/bar/idk.py'

        remote.upload_file(local_path, remote_path)

        ssh.assert_not_called()

        ftp.assert_has_calls(
            [call.put(ANY, '/foo/bar/idk.py'),
             call.chmod('/foo/bar/idk.py', ANY)], any_order=False)

    def test_upload_files(self):
        """ Test run command map upload_repo_files """

        # test upload_files
        with patch('host.RemoteHost') as mongod:
            command = {"upload_files": [{"target": "remote_path", "source": "mongos.log"}]}
            host._run_host_command_map(mongod, command, "test_id")
            mongod.upload_file.assert_called_once_with("mongos.log", "remote_path")

        with patch('host.RemoteHost') as mongod:
            command = {
                "upload_files": [{
                    "source": "mongos.log",
                    "target": "remote_path"
                }, {
                    "source": "to",
                    "target": "from"
                }]
            }
            host._run_host_command_map(mongod, command, "test_id")
            calls = [mock.call("mongos.log", "remote_path"), mock.call("to", "from")]
            mongod.upload_file.assert_has_calls(calls, any_order=True)

    def test_retrieve_files(self):
        """ Test run command map upload_repo_files """

        # retrieve_files tests
        with patch('host.RemoteHost') as mongod:
            mock_retrieve_file = Mock()
            mongod.retrieve_path = mock_retrieve_file

            command = {"retrieve_files": [{"source": "remote_path", "target": "mongos.log"}]}
            mongod.alias = 'host'
            host._run_host_command_map(mongod, command, "test_id")
            mock_retrieve_file.assert_any_call("remote_path", "reports/test_id/host/mongos.log")

        # retrieve_files tests
        with patch('host.RemoteHost') as mongod:
            mock_retrieve_file = Mock()
            mongod.retrieve_path = mock_retrieve_file

            command = {"retrieve_files": [{"source": "remote_path", "target": "mongos.log"}]}
            mongod.alias = 'host'
            host._run_host_command_map(mongod, command, "test_id")
            mock_retrieve_file.assert_any_call("remote_path", "reports/test_id/host/mongos.log")

        with patch('host.RemoteHost') as mongod:
            mock_retrieve_file = Mock()
            mongod.retrieve_path = mock_retrieve_file

            command = {"retrieve_files": [{"source": "remote_path", "target": "local_path"}]}
            mongod.alias = 'host'
            host._run_host_command_map(mongod, command, "test_id")
            mock_retrieve_file.assert_any_call("remote_path", "reports/test_id/host/local_path")

        with patch('host.RemoteHost') as mongod:
            mock_retrieve_file = Mock()
            mongod.retrieve_path = mock_retrieve_file

            mongod.alias = "mongod.0"
            host._run_host_command_map(mongod, command, "test_id")
            mock_retrieve_file.assert_any_call("remote_path", "reports/test_id/mongod.0/local_path")

        with patch('host.RemoteHost') as mongod:
            mock_retrieve_file = Mock()
            mongod.retrieve_path = mock_retrieve_file

            command = {"retrieve_files": [{"source": "remote_path", "target": "./local_path"}]}
            mongod.alias = "mongos.0"
            host._run_host_command_map(mongod, command, "test_id")
            mock_retrieve_file.assert_any_call("remote_path", "reports/test_id/mongos.0/local_path")

    def test_exec(self):
        """ Test run command map upload_repo_files """

        # test exec
        with patch('host.RemoteHost') as mongod:
            command = {"exec": "this is a command"}
            host._run_host_command_map(mongod, command, "test_id")
            mongod.run.assert_called_once_with(["this", "is", "a", "command"])

    def test_exec_mongo_shell(self):
        """ Test run command map upload_repo_files """

        # test exec_mongo_shell
        with patch('host.RemoteHost') as mongod:
            command = {
                "exec_mongo_shell": {
                    "script": "this is a script",
                    "connection_string": "connection string"
                }
            }
            host._run_host_command_map(mongod, command, "test_id")
            mongod.exec_mongo_command.assert_called_once_with(
                "this is a script", connection_string="connection string")

        with patch('host.RemoteHost') as mongod:
            command = {"exec_mongo_shell": {"script": "this is a script"}}
            host._run_host_command_map(mongod, command, "test_id")
            mongod.exec_mongo_command.assert_called_once_with(
                "this is a script", connection_string="")

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

    def test_local_host_exec_command(self):
        """ Test LocalHost.exec_command """

        local = host.LocalHost()
        common.utils.mkdir_p(os.path.dirname(self.filename))

        self.assertEqual(local.exec_command('exit 0'), 0)

        # test that the correct warning is issued
        mock_logger = MagicMock(name='LOG')
        host.LOG.warn = mock_logger
        self.assertEqual(local.exec_command('exit 1'), 1)
        mock_logger.assert_called_once_with(ANY_IN_STRING('Failed with exit status'), ANY, ANY, ANY)

        local.exec_command('touch {}'.format(self.filename))
        self.assertTrue(os.path.isfile(self.filename))

        local.exec_command('touch {}'.format(self.filename))
        self.assertTrue(os.path.isfile(self.filename))

        with open(self.filename, 'w+') as the_file:
            the_file.write('Hello\n')
            the_file.write('World\n')
        out = StringIO()
        err = StringIO()
        local.exec_command('cat {}'.format(self.filename), out, err)
        self.assertEqual(out.getvalue(), "Hello\nWorld\n")

        out = StringIO()
        err = StringIO()
        self.assertEqual(local.exec_command('cat {}; exit 1'.format(self.filename), out, err), 1)
        self.assertEqual(out.getvalue(), "Hello\nWorld\n")
        self.assertEqual(err.getvalue(), "")

        out = StringIO()
        err = StringIO()
        local.exec_command('cat {} >&2; exit 1'.format(self.filename), out, err)
        self.assertEqual(out.getvalue(), "")
        self.assertEqual(err.getvalue(), "Hello\nWorld\n")

        out = StringIO()
        err = StringIO()
        command = """cat {filename} && cat -n {filename} >&2; \
        exit 1""".format(filename=self.filename)
        local.exec_command(command, out, err)
        self.assertEqual(out.getvalue(), "Hello\nWorld\n")
        self.assertEqual(err.getvalue(), "     1\tHello\n     2\tWorld\n")

        out = StringIO()
        err = StringIO()
        command = "seq 10 -1 1 | xargs  -I % sh -c '{ echo %; sleep .1; }'; \
        echo 'blast off!'"

        local.exec_command(command, out, err)
        self.assertEqual(out.getvalue(), "10\n9\n8\n7\n6\n5\n4\n3\n2\n1\nblast off!\n")
        self.assertEqual(err.getvalue(), "")

        # test timeout and that the correct warning is issued
        out = StringIO()
        err = StringIO()
        command = "sleep 1"

        mock_logger = MagicMock(name='LOG')
        host.LOG.warn = mock_logger
        self.assertEqual(local.exec_command(command, out, err, max_time_ms=500), 1)
        mock_logger.assert_called_once_with(ANY_IN_STRING('Timeout after'), ANY, ANY, ANY, ANY)

    def test_local_host_tee(self):
        """ Test run command map retrieve_files """

        local = host.LocalHost()
        common.utils.mkdir_p(os.path.dirname(self.filename))

        expected = "10\n9\n8\n7\n6\n5\n4\n3\n2\n1\nblast off!\n"
        with open(self.filename, "w") as the_file:
            out = StringIO()
            tee = TeeStream(the_file, out)
            err = StringIO()
            command = "seq 10 -1 1 | xargs  -I % sh -c '{ echo %; sleep .1; }'; \
        echo 'blast off!'"

            local.exec_command(command, tee, err)
            self.assertEqual(out.getvalue(), expected)
            self.assertEqual(err.getvalue(), "")

        with open(self.filename) as the_file:
            self.assertEqual(expected, "".join(the_file.readlines()))

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
        remote._retrieve_file('remote_file', 'reports/local_file')

        remote.ftp.get.assert_called_with('remote_file', 'reports/local_file')
        mock_makedirs.assert_not_called()

        mock_exists.return_value = True
        remote = host.RemoteHost('53.1.1.1', "ssh_user", "ssh_key_file")
        remote._retrieve_file('remote_file', 'reports/mongod.0/local_file')

        remote.ftp.get.assert_called_with('remote_file', 'reports/mongod.0/local_file')
        mock_makedirs.assert_not_called()

        mock_exists.return_value = True
        remote = host.RemoteHost('53.1.1.1', "ssh_user", "ssh_key_file")
        remote._retrieve_file('remote_file', 'reports/../local_file')

        remote.ftp.get.assert_called_with('remote_file', 'local_file')
        mock_makedirs.assert_not_called()

        mock_exists.return_value = False
        remote = host.RemoteHost('53.1.1.1', "ssh_user", "ssh_key_file")
        remote._retrieve_file('remote_file', 'reports/local_file')

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
        remote.retrieve_path('remote_file', 'reports/local_file')

        remote.remote_isdir.assert_not_called()

        # remote path is a single file
        remote.remote_exists.reset_mock()
        remote.remote_isdir.reset_mock()
        remote._retrieve_file.reset_mock()
        remote.ftp.listdir.reset_mock()

        remote.remote_exists.return_value = True
        remote.remote_isdir.return_value = False
        remote.retrieve_path('remote_file', 'reports/local_file')
        remote._retrieve_file.assert_called_with('remote_file', 'reports/local_file')

        # remote path is a directory containing a single file
        remote.remote_exists.reset_mock()
        remote.remote_isdir.reset_mock()
        remote._retrieve_file.reset_mock()
        remote.ftp.listdir.reset_mock()

        remote.remote_exists.return_value = True
        isdir_map = {'remote_dir': True}
        remote.remote_isdir.side_effect = lambda name: isdir_map.get(name, False)
        remote.ftp.listdir.return_value = ['mongod.log']

        remote.retrieve_path('remote_dir', 'reports/local_dir')

        remote.ftp.listdir.assert_called_with('remote_dir')
        remote._retrieve_file.assert_called_with('remote_dir/mongod.log',
                                                 'reports/local_dir/mongod.log')

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

        remote.retrieve_path('remote_dir', 'reports/local_dir')

        remote.ftp.listdir.assert_called_with('remote_dir')
        self.assertTrue(remote._retrieve_file.mock_calls == [
            mock.call('remote_dir/mongod.log', 'reports/local_dir/mongod.log'),
            mock.call('remote_dir/metrics.2017-04-27T09-14-33Z-00000',
                      'reports/local_dir/metrics.2017-04-27T09-14-33Z-00000'),
            mock.call('remote_dir/metrics.interim', 'reports/local_dir/metrics.interim')
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

        remote.retrieve_path('remote_dir', 'reports/local_dir')
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

        remote.retrieve_path('remote_dir', 'reports/local_dir')
        self.assertTrue(
            remote.ftp.listdir.mock_calls ==
            [mock.call('remote_dir'), mock.call('remote_dir/data')])
        # remote.ftp.listdir.assert_called_with('remote_dir')
        remote._retrieve_file.assert_called_with('remote_dir/data/metrics.interim',
                                                 'reports/local_dir/data/metrics.interim')

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

        remote.retrieve_path('remote_dir', 'reports/local_dir')
        remote.ftp.listdir.assert_called_with('remote_dir')
        self.assertTrue(remote._retrieve_file.mock_calls == [
            mock.call('remote_dir/data', 'reports/local_dir/data'),
            mock.call('remote_dir/logs', 'reports/local_dir/logs')
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

        remote.retrieve_path('remote_dir', 'reports/local_dir')

        # note empty is not here so it was not called
        self.assertTrue(remote._retrieve_file.mock_calls == [
            mock.call('remote_dir/data/metrics.interim', 'reports/local_dir/data/metrics.interim'),
            mock.call('remote_dir/data/metrics.2017-04-27T09-14-33Z-00000',
                      'reports/local_dir/data/metrics.2017-04-27T09-14-33Z-00000'),
            mock.call('remote_dir/file', 'reports/local_dir/file'),
            mock.call('remote_dir/logs/mongod.log', 'reports/local_dir/logs/mongod.log')
        ])

    @patch("bin.common.host._run_host_command_map")
    def test_exec_mongo_command(self, mock_run_host_command_map):
        """ Test run RemoteHost.exec_mongo_command """

        with patch('bin.common.host.make_host') as mock_make_host:
            mock_target_host = Mock()
            mock_make_host.return_value = mock_target_host
            make_host_runner("host_info", 'command', "ssh_user", "ssh_key_file", "test_id")
            mock_make_host.assert_called_once_with("host_info", "ssh_user", "ssh_key_file")
            mock_target_host.run.assert_called_once_with('command')
            mock_target_host.close.assert_called_once()

        with patch('bin.common.host.make_host') as mock_make_host:
            command = {}
            mock_target_host = Mock()
            mock_make_host.return_value = mock_target_host
            make_host_runner("host_info", command, "ssh_user", "ssh_key_file", 'test_id')
            mock_make_host.assert_called_once_with("host_info", "ssh_user", "ssh_key_file")
            mock_run_host_command_map.assert_called_once_with(mock_target_host, command, 'test_id')
            mock_target_host.close.assert_called_once()

    @patch("host.RemoteHost.exec_command")
    @patch("host.RemoteHost.create_file")
    @patch('paramiko.SSHClient')
    def test_make_host_runner(self, mock_ssh, mock_create_file, mock_exec_command):
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
        mock_exec_command.assert_called_with(test_argv, max_time_ms=None)

    @patch('paramiko.SSHClient')
    def test_remote_host(self, mock_paramiko):
        """Test RemoteHost constructor exception handling"""

        # test exit call on paramiko and socket exceptions
        with self.assertRaises(SystemExit):
            mock_ssh = MagicMock(name='connection')
            mock_paramiko.return_value = mock_ssh

            mock_ssh.connect.side_effect = paramiko.SSHException()
            host.RemoteHost('test_host', 'test_user', 'test_pem_file')

        with self.assertRaises(SystemExit):
            mock_ssh = MagicMock(name='connection')
            mock_paramiko.return_value = mock_ssh

            mock_ssh.connect.side_effect = socket.error()
            host.RemoteHost('test_host', 'test_user', 'test_pem_file')

        # test other exceptions are thrown to caller
        with self.assertRaises(Exception):
            mock_ssh = MagicMock(name='connection')
            mock_paramiko.return_value = mock_ssh

            mock_ssh.connect.side_effect = Exception()
            host.RemoteHost('test_host', 'test_user', 'test_pem_file')

    @patch('paramiko.SSHClient')
    def test_run(self, mock_ssh):
        """Test RemoteHost.run"""
        subject = host.RemoteHost('test_host', 'test_user', 'test_pem_file')

        # test string command
        subject.exec_command = MagicMock(name='exec_command')
        subject.exec_command.return_value = 0
        self.assertTrue(subject.run('cowsay Hello World'))
        subject.exec_command.assert_called_once_with('cowsay Hello World')

        # Test fail
        subject.exec_command = MagicMock(name='exec_command')
        subject.exec_command.return_value = 1
        self.assertFalse(subject.run('cowsay Hello World'))
        subject.exec_command.assert_called_once_with('cowsay Hello World')

        # test list command success
        subject.exec_command = MagicMock(name='exec_command')
        subject.exec_command.return_value = 0
        self.assertTrue(subject.run([['cowsay', 'Hello', 'World'], ['cowsay', 'moo']]))
        subject.exec_command.assert_any_call(['cowsay', 'Hello', 'World'])
        subject.exec_command.assert_any_call(['cowsay', 'moo'])

        # test list command failure
        subject.exec_command = MagicMock(name='exec_command')
        subject.exec_command.side_effect = [0, 1, 0]
        self.assertFalse(
            subject.run([['cowsay', 'Hello', 'World'], ['cowsay', 'moo'], ['cowsay', 'boo']]))
        calls = [
            mock.call(['cowsay', 'Hello', 'World']),
            mock.call(['cowsay', 'moo']),
        ]
        subject.exec_command.assert_has_calls(calls)

        # test list command failure
        subject.exec_command = MagicMock(name='exec_command')
        subject.exec_command.return_value = 0
        self.assertTrue(subject.run(['cowsay Hello World', 'cowsay moo']))
        subject.exec_command.assert_called_once_with(['cowsay Hello World', 'cowsay moo'])

    # normally wouldn't test internal method, but the collaboration with other
    # objects is complicated within host.exec_command and leads to the core logic
    # being hard to isolate on its own.
    def when_perform_exec(self, case):
        """
        :param case: contains given/then conditions for behavior of _perform_exec

        Example:

            'given': {
                # params given to _perform_exec
                'command': 'cowsay HellowWorld',
                'max_timeout_ms': 750,
                'no_output_timeout_ms': 20,
                # mock _stream behavior
                'ssh_interrupt_after_ms': 5,
                'with_output': False,
                # (was exist status ready, actual exit status)
                'and_exit_status': (True, 0),
            },
            'then': {
                # asserted output of _perform_exec
                'exit_status': 0,
                'did_timeout': False,
                'time_taken_seconds': ANY
            }
        """
        given = case['given']
        then = case.get('then', None)

        new_mock = lambda name: MagicMock(autospec=True, name=name)
        (stdout, stderr, ssh_stdout, ssh_stderr) = (new_mock('stdout'), new_mock('stderr'),
                                                    new_mock('ssh_stdout'), new_mock('ssh_stderr'))

        ssh_stdout.channel.exit_status_ready.return_value = given['and_exit_status'][0]
        ssh_stdout.channel.recv_exit_status.return_value = given['and_exit_status'][1]

        stream_before = host._stream
        with patch('paramiko.SSHClient', autospec=True):
            try:
                # monkey-patch here because @patch doesn't let us (easily) change
                # the actual behavior of the method, just set canned return values and
                # assert interactions. We actually want _stream() to sleep as well
                host._stream = sleepy_streamer(
                    float(given['ssh_interrupt_after_ms']) / 1000, given['with_output'])

                remote_host = host.RemoteHost('test_host', 'test_user', 'test_pem_file')
                exit_status = remote_host._perform_exec(
                    given['command'],
                    stdout,
                    stderr,
                    ssh_stdout,
                    ssh_stderr,
                    given['max_timeout_ms'],
                    given['no_output_timeout_ms'],
                )

                if then:
                    self.assertEqual(then, {'exit_status': exit_status})
            finally:
                host._stream = stream_before

    def test_perform_exec_no_timeout(self):
        """test_perform_exec_no_timeout"""
        self.when_perform_exec({
            'given': {
                'command': 'cowsay Hello World',
                'max_timeout_ms': 100,
                'no_output_timeout_ms': 20,
                'ssh_interrupt_after_ms': 5,
                'with_output': False,
                'and_exit_status': (True, 0),
            },
            'then': {
                'exit_status': 0
            }
        })

    def test_perform_exec_no_output(self):
        """
        This one times out because of the
        False in and_exit_status[0].
        The ssh never finishes and doesn't produce
        output, so it's a timeout.
        """

        with self.assertRaisesRegexp(host.HostException, r'^No Output'):
            self.when_perform_exec({
                'given': {
                    'command': 'cowsay Hello World',
                    'max_timeout_ms': 100,
                    'no_output_timeout_ms': 20,
                    'ssh_interrupt_after_ms': 5,
                    'with_output': False,
                    'and_exit_status': (False, 10),
                }
            })

    def test_perform_exec_max_timeout(self):
        """
        This one times out because of the
        False in and_exit_status[0].
        The ssh never finishes and doesn't produce
        output, so it's a timeout.
        """

        with self.assertRaisesRegexp(host.HostException, r'exceeded [0-9\.]+ allowable seconds on'):
            self.when_perform_exec({
                'given': {
                    'command': 'cowsay Hello World',
                    'max_timeout_ms': 200,
                    'no_output_timeout_ms': 1000000,
                    'ssh_interrupt_after_ms': 5,
                    'with_output': True,
                    'and_exit_status': (False, 10),
                }
            })

    def test_perform_exec_ready(self):
        """test_perform_exec_ready"""
        self.when_perform_exec({
            'given': {
                'command': 'cowsay Hello World',
                'max_timeout_ms': 100,
                'no_output_timeout_ms': 20,
                'ssh_interrupt_after_ms': 5,
                'with_output': False,
                'and_exit_status': (True, 2),
            },
            'then': {
                'exit_status': 2
            }
        })

    def test_perform_exec_total_timeout_no_output(self):
        """test_perform_exec_total_timeout_no_output"""
        with self.assertRaisesRegexp(host.HostException, r'^No Output'):
            self.when_perform_exec({
                'given': {
                    'command': 'cowsay Hello World',
                    'max_timeout_ms': 20,
                    'no_output_timeout_ms': 10,
                    'ssh_interrupt_after_ms': 5,
                    'with_output': False,
                    'and_exit_status': (False, 0),
                }
            })

    def test_perform_exec_immediate_fail(self):
        """test_perform_exec_total_timeout_no_output"""
        self.when_perform_exec({
            'given': {
                'command': 'cowsay Hello World',
                'max_timeout_ms': 20,
                'no_output_timeout_ms': 10,
                'ssh_interrupt_after_ms': 1,
                'with_output': True,
                'and_exit_status': (True, 127),
            },
            'then': {
                'exit_status': 127
            }
        })

    # pylint: disable=too-many-statements
    def test_remote_exec_command(self):
        """Test RemoteHost.exec_command"""

        def _test_common(command='cowsay Hello World',
                         expected='cowsay Hello World',
                         return_value=0,
                         exit_status=0):
            """ test common code with """
            remote_host = host.RemoteHost('test_host', 'test_user', 'test_pem_file')

            ssh_instance = mock_ssh.return_value
            stdin = Mock(name='stdin')

            # magic mock for iterable support
            stdout = mock.MagicMock(name='stdout')
            stdout.__iter__.return_value = ''

            stderr = mock.MagicMock(name='stderr')
            stdout.__iter__.return_value = ''
            ssh_instance.exec_command.return_value = [stdin, stdout, stderr]

            # Test a command as string
            out = StringIO()
            err = StringIO()

            remote_host._perform_exec = mock.MagicMock(name='_perform_exec')
            remote_host._perform_exec.return_value = exit_status

            self.assertEqual(remote_host.exec_command(command, out, err), return_value)
            ssh_instance.exec_command.assert_called_once_with(expected, get_pty=False)
            stdin.channel.shutdown_write.assert_called_once()

            stdin.close.assert_called()
            stdout.close.assert_called()
            stderr.close.assert_called()

        # Exceptions
        with patch('paramiko.SSHClient') as mock_ssh:
            remote_host = host.RemoteHost('test_host', 'test_user', 'test_pem_file')

            # Test error cases
            with self.assertRaises(ValueError):
                remote_host.exec_command('')

            with self.assertRaises(ValueError):
                remote_host.exec_command([])

            # Anything else should fail
            with self.assertRaises(ValueError):
                remote_host.exec_command(None)

            with self.assertRaises(ValueError):
                remote_host.exec_command(0)

        # list and string
        with patch('paramiko.SSHClient') as mock_ssh:
            _test_common()

        with patch('paramiko.SSHClient') as mock_ssh:
            mock_logger = MagicMock(name='LOG')
            host.LOG.warn = mock_logger
            _test_common(command=['cowsay', 'Hello', 'World'])
            mock_logger.assert_not_called()

        with patch('paramiko.SSHClient') as mock_ssh:
            mock_logger = MagicMock(name='LOG')
            host.LOG.warn = mock_logger
            _test_common(return_value=1, exit_status=1)
            mock_logger.assert_called_once_with(ANY_IN_STRING('with exit status'), ANY, ANY, ANY)

        with patch('paramiko.SSHClient') as mock_ssh:
            # Test a command as list
            remote_host = host.RemoteHost('test_host', 'test_user', 'test_pem_file')

            ssh_instance = mock_ssh.return_value
            stdin = Mock(name='stdin')

            # magic mock for iterable support
            stdout = mock.MagicMock(name='stdout')
            stdout.__iter__.return_value = ['1', '2', '3', '', '3', '2', '1']
            stdout.channel.recv_exit_status.return_value = [True, False]

            stderr = mock.MagicMock(name='stderr')
            stderr.__iter__.return_value = ['First', 'Second', 'Third']

            ssh_instance.exec_command.return_value = [stdin, stdout, stderr]

            stdout.channel.exit_status_ready.return_value = True

            # Test a command as string
            out = StringIO()
            err = StringIO()

            remote_host._perform_exec = mock.MagicMock(name='_perform_exec')
            remote_host._perform_exec.return_value = 0

            remote_host.exec_command(
                'command',
                out,
                err,
                max_time_ms='max_time_ms',
                no_output_timeout_ms='no_output_timeout_ms')
            ssh_instance.exec_command.assert_called_once_with('command', get_pty=False)
            stdin.channel.shutdown_write.assert_called_once()
            stdin.close.assert_called()
            stdout.close.assert_called()
            stderr.close.assert_called()

            remote_host._perform_exec.assert_called_once_with('command', out, err, stdout, stderr,
                                                              'max_time_ms', 'no_output_timeout_ms')

    def test_checkout_repos(self):
        """
        Test Host.checkout_repos command
        """
        # Only testing on LocalHost since `checkout_repos` is implemented in the base class and not
        # overidden
        local_host = host.LocalHost()

        # Test with existing target that is not a git repository
        source = 'git@github.com:mongodb/mongo.git'
        target = os.path.expanduser('~')
        command = ['cd', target, '&&', 'git', 'status']
        with patch('host.mkdir_p') as mock_mkdir_p, \
             patch('host.LocalHost.exec_command') as mock_exec_command:
            self.assertRaises(UserWarning, local_host.checkout_repos, source, target)
            mock_mkdir_p.assert_not_called()
            mock_exec_command.assert_called_once()
            mock_exec_command.assert_called_with(command)

        # Test with non-existing target
        parent_dir = os.path.join(os.path.expanduser('~'), 'checkout_repos_test')
        source = 'https://github.com/mongodb/stitch-js-sdk.git'
        target = os.path.join(parent_dir, 'stitch-js-sdk')
        command = ['git', 'clone', source, target]
        self.assertFalse(os.path.exists(target))
        with patch('host.mkdir_p') as mock_mkdir_p, \
             patch('host.LocalHost.exec_command') as mock_exec_command:
            local_host.checkout_repos(source, target)
            mock_mkdir_p.assert_called_with(parent_dir)
            mock_exec_command.assert_called_once()
            mock_exec_command.assert_called_with(command)

        # Test with existing target that is a git repository
        command = ['cd', target, '&&', 'git', 'status']
        with patch('host.os.path.isdir') as mock_isdir, \
             patch('host.mkdir_p') as mock_mkdir_p, \
             patch('host.LocalHost.exec_command') as mock_exec_command:
            mock_isdir.return_value = True
            mock_exec_command.return_value = 0
            local_host.checkout_repos(source, target)
            mock_mkdir_p.assert_not_called()
            mock_exec_command.assert_called_once()
            mock_exec_command.assert_called_with(command)

        # Test with specified branch
        branch = '2.x.x'
        commands = [['git', 'clone', source, target],
                    ['cd', target, '&&', 'git', 'checkout', branch]]
        self.assertFalse(os.path.exists(target))
        with patch('host.mkdir_p') as mock_mkdir_p, \
             patch('host.LocalHost.exec_command') as mock_exec_command:
            local_host.checkout_repos(source, target, branch)
            mock_mkdir_p.assert_called_with(parent_dir)
            self.assertEqual(mock_exec_command.call_count, 2)
            mock_exec_command.assert_any_call(commands[0])
            mock_exec_command.assert_any_call(commands[1])


if __name__ == '__main__':
    unittest.main()
