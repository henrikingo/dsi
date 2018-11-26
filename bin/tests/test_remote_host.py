"""Tests for bin/common/remote_host.py"""

import collections
import os
import socket
import stat
import time
import unittest
from StringIO import StringIO

import paramiko
from mock import patch, call, mock, ANY, MagicMock, Mock

import common.host_utils
import common.command_runner
import common.remote_host
from common.mongodb_setup_helpers import MongoDBAuthSettings
from test_lib.comparator_utils import ANY_IN_STRING

FakeStat = collections.namedtuple('FakeStat', 'st_mode')


def sleepy_streamer(sleep_time_sec, outval):
    """
    :param sleep_time_sec: how long in seconds to sleep
    :param outval: forced return value
    :return: a function that sleeps for `sleep_time_sec` seconds and returns `outval`
    """

    def out(io1, io2):
        time.sleep(sleep_time_sec)
        return outval

    return out


class RemoteHostTestCase(unittest.TestCase):
    """ Unit Test for RemoteHost library """

    @patch('common.host_utils.connected_ssh')
    def test_upload_files_dir(self, mock_connected_ssh):
        """We can upload directories of files"""

        ssh = mock.MagicMock(name='ssh')
        ftp = mock.MagicMock(name='ftp')
        channel = mock.MagicMock(name='channel')
        ssh.exec_command.return_value = channel, channel, channel

        mock_connected_ssh.return_value = (ssh, ftp)

        remote = common.remote_host.RemoteHost(host=None, user=None, pem_file=None)
        remote._perform_exec = mock.MagicMock(name='_perform_exec')
        remote._perform_exec.return_value = 0

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

    @patch('common.host_utils.connected_ssh')
    def test_upload_single_file(self, mock_connected_ssh):
        """We can upload a single file"""
        ssh = mock.MagicMock(name='ssh')
        ftp = mock.MagicMock(name='ftp')
        mock_connected_ssh.return_value = (ssh, ftp)

        remote = common.remote_host.RemoteHost(host=None, user=None, pem_file=None)

        local_path = os.path.abspath(__file__)
        remote_path = '/foo/bar/idk.py'

        remote.upload_file(local_path, remote_path)

        ssh.assert_not_called()

        ftp.assert_has_calls(
            [call.put(ANY, '/foo/bar/idk.py'),
             call.chmod('/foo/bar/idk.py', ANY)], any_order=False)

    @patch('paramiko.SSHClient')
    def test__upload_files_host_ex(self, ssh_client):
        """ Test run command map excpetion """

        with self.assertRaisesRegexp(common.host_utils.HostException, r'wrapped exception'):
            remote = common.remote_host.RemoteHost('53.1.1.1', "ssh_user", "ssh_key_file")
            command = {"upload_files": [{"target": "remote_path", "source": "."}]}
            remote.exec_command = MagicMock(name='exec_command')
            remote.exec_command.return_value = 0

            remote._upload_single_file = MagicMock(name='_upload_single_file')
            remote._upload_single_file.side_effect = paramiko.ssh_exception.SSHException(
                "wrapped exception")
            common.command_runner._run_host_command_map(remote, command, "test_id")

    @patch('paramiko.SSHClient')
    def test__upload_files_wrapped_ex(self, ssh_client):
        """ Test run command map excpetion """

        with self.assertRaisesRegexp(common.host_utils.HostException,
                                     r"'mkdir', '-p', 'remote_path'"):
            remote = common.remote_host.RemoteHost('53.1.1.1', "ssh_user", "ssh_key_file")
            command = {"upload_files": [{"target": "remote_path", "source": "."}]}
            remote.exec_command = MagicMock(name='exec_command')
            remote.exec_command.return_value = 1

            remote._upload_single_file = MagicMock(name='_upload_single_file')
            remote._upload_single_file.side_effect = paramiko.ssh_exception.SSHException(
                "wrapped exception")
            common.command_runner._run_host_command_map(remote, command, "test_id")

    @patch('paramiko.SSHClient')
    def test_remote_host_isdir(self, mock_ssh):
        """ Test remote_isdir """

        remote = common.remote_host.RemoteHost('53.1.1.1', "ssh_user", "ssh_key_file")
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

        remote = common.remote_host.RemoteHost('53.1.1.1', "ssh_user", "ssh_key_file")
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

        remote = common.remote_host.RemoteHost('53.1.1.1', "ssh_user", "ssh_key_file")
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

        remote = common.remote_host.RemoteHost('53.1.1.1', "ssh_user", "ssh_key_file")
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
        remote = common.remote_host.RemoteHost('53.1.1.1', "ssh_user", "ssh_key_file")
        remote._retrieve_file('remote_file', 'reports/local_file')

        remote.ftp.get.assert_called_with('remote_file', 'reports/local_file')
        mock_makedirs.assert_not_called()

        mock_exists.return_value = True
        remote = common.remote_host.RemoteHost('53.1.1.1', "ssh_user", "ssh_key_file")
        remote._retrieve_file('remote_file', 'reports/mongod.0/local_file')

        remote.ftp.get.assert_called_with('remote_file', 'reports/mongod.0/local_file')
        mock_makedirs.assert_not_called()

        mock_exists.return_value = True
        remote = common.remote_host.RemoteHost('53.1.1.1', "ssh_user", "ssh_key_file")
        remote._retrieve_file('remote_file', 'reports/../local_file')

        remote.ftp.get.assert_called_with('remote_file', 'local_file')
        mock_makedirs.assert_not_called()

        mock_exists.return_value = False
        remote = common.remote_host.RemoteHost('53.1.1.1', "ssh_user", "ssh_key_file")
        remote._retrieve_file('remote_file', 'reports/local_file')

        remote.ftp.get.assert_called_with('remote_file', 'reports/local_file')
        mock_makedirs.assert_called_with('reports')

    @patch('paramiko.SSHClient')
    def test_retrieve_file_for_files(self, mock_ssh):
        """ Test run RemoteHost.exists """

        # remote path does not exist
        remote = common.remote_host.RemoteHost('53.1.1.1', "ssh_user", "ssh_key_file")
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

        remote = common.remote_host.RemoteHost('53.1.1.1', "ssh_user", "ssh_key_file")
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

        remote = common.remote_host.RemoteHost('53.1.1.1', "ssh_user", "ssh_key_file")
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

    def helper_exec_mongo_command(
            self,
            connection_string='mongodb://test_connection_string',
            mongodb_auth_settings=None,
            expect_auth_command_line=True,
    ):
        """ Test run RemoteHost.exec_mongo_command """

        # We define an extra function for setting up the mocked values in order to make the
        # 'connection_string' and 'mongodb_auth_settings' parameters optional.
        @patch("common.remote_host.RemoteHost.exec_command")
        @patch("common.remote_host.RemoteHost.create_file")
        @patch('paramiko.SSHClient')
        def run_test(mock_ssh, mock_create_file, mock_exec_command):
            mock_exec_command.return_value = 0
            test_file = 'test_file'
            test_user = 'test_user'
            test_pem_file = 'test_pem_file'
            test_host = 'test_host'
            test_script = 'test_script'
            expected_argv = ['bin/mongo', '--verbose']
            if mongodb_auth_settings is not None and expect_auth_command_line:
                expected_argv.extend(
                    ['-u', 'username', '-p', 'password', '--authenticationDatabase', 'admin'])
            expected_argv.extend(['"' + connection_string + '"', test_file])
            remote = common.remote_host.RemoteHost(test_host, test_user, test_pem_file,
                                                   mongodb_auth_settings)
            status_code = remote.exec_mongo_command(test_script, test_file, connection_string)
            self.assertEqual(0, status_code)
            mock_create_file.assert_called_with(test_file, test_script)
            mock_exec_command.assert_called_with(
                expected_argv, stdout=None, stderr=None, max_time_ms=None, quiet=False)

        run_test()

    def test_exec_mongo_command_no_auth(self):
        self.helper_exec_mongo_command()

    def test_exec_mongo_command_with_auth_settings(self):
        self.helper_exec_mongo_command(
            mongodb_auth_settings=MongoDBAuthSettings('username', 'password'))

    def test_exec_mongo_command_with_auth_connection_string(self):
        self.helper_exec_mongo_command(
            connection_string="mongodb://username:password@test_connection_string")

        self.assertRaisesRegexp(
            ValueError,
            "Must specify both username and password",
            self.helper_exec_mongo_command,
            connection_string="mongodb://username@test_connection_string")

    def test_exec_mongo_command_with_auth_settings_and_connection_string(self):
        self.helper_exec_mongo_command(
            connection_string="mongodb://username:password@test_connection_string",
            mongodb_auth_settings=MongoDBAuthSettings('username', 'password'),
            expect_auth_command_line=False)

        self.assertRaisesRegexp(
            ValueError,
            "Username.*doesn't match",
            self.helper_exec_mongo_command,
            connection_string="mongodb://username:password@test_connection_string",
            mongodb_auth_settings=MongoDBAuthSettings('username2', 'password'))

        self.assertRaisesRegexp(
            ValueError,
            "Password.*doesn't match",
            self.helper_exec_mongo_command,
            connection_string="mongodb://username:password@test_connection_string",
            mongodb_auth_settings=MongoDBAuthSettings('username', 'password2'))

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

        stream_before = common.host_utils.stream_lines
        with patch('paramiko.SSHClient', autospec=True):
            try:
                # monkey-patch here because @patch doesn't let us (easily) change
                # the actual behavior of the method, just set canned return values and
                # assert interactions. We actually want _stream() to sleep as well
                common.host_utils.stream_lines = sleepy_streamer(
                    float(given['ssh_interrupt_after_ms']) / 1000, given['with_output'])

                remote = common.remote_host.RemoteHost('test_host', 'test_user', 'test_pem_file')
                exit_status = remote._perform_exec(
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
                common.host_utils.stream_lines = stream_before

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

        with self.assertRaisesRegexp(common.host_utils.HostException, r'^No Output'):
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

        with self.assertRaisesRegexp(common.host_utils.HostException,
                                     r'exceeded [0-9\.]+ allowable seconds on'):
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
        with self.assertRaisesRegexp(common.host_utils.HostException, r'^No Output'):
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

    @patch('paramiko.SSHClient')
    def helper_remote_exec_command(self,
                                   mock_ssh,
                                   command='cowsay Hello World',
                                   expected='cowsay Hello World',
                                   return_value=0,
                                   exit_status=0,
                                   out=StringIO(),
                                   err=StringIO()):
        """ test common code with """
        remote = common.remote_host.RemoteHost('test_host', 'test_user', 'test_pem_file')

        ssh_instance = mock_ssh.return_value
        stdin = Mock(name='stdin')

        # magic mock for iterable support
        stdout = mock.MagicMock(name='stdout')
        stdout.__iter__.return_value = ''

        stderr = mock.MagicMock(name='stderr')
        stdout.__iter__.return_value = ''
        ssh_instance.exec_command.return_value = [stdin, stdout, stderr]

        remote._perform_exec = mock.MagicMock(name='_perform_exec')
        remote._perform_exec.return_value = exit_status

        self.assertEqual(remote.exec_command(command, out, err), return_value)
        ssh_instance.exec_command.assert_called_once_with(expected, get_pty=False)
        stdin.channel.shutdown_write.assert_called_once()

        stdin.close.assert_called()
        stdout.close.assert_called()
        stderr.close.assert_called()

    def helper_remote_exec_command_ex(self, params='', exception=ValueError):
        """Test RemoteHost.exec_command"""
        # Exceptions
        with patch('paramiko.SSHClient'):
            remote = common.remote_host.RemoteHost('test_host', 'test_user', 'test_pem_file')
            self.assertRaises(exception, remote.exec_command, params)

    def test_remote_exec_command_ex_str(self):
        """Test RemoteHost.exec_command exceptions '' param """
        self.helper_remote_exec_command_ex()

    def test_remote_exec_command_ex_array(self):
        """Test RemoteHost.exec_command exceptions [] param  """
        self.helper_remote_exec_command_ex(params=[])

    def test_remote_exec_command_ex_none(self):
        """Test RemoteHost.exec_command exceptions None  param  """
        self.helper_remote_exec_command_ex(params=None)

    def test_remote_exec_command_ex_zero(self):
        """Test RemoteHost.exec_command exceptions 0  param   """
        self.helper_remote_exec_command_ex(params=0)

    def test_remote_exec_command(self):
        """Test RemoteHost.exec_command"""
        self.helper_remote_exec_command()

    def test_remote_exec_command_no_warn(self):
        """Test RemoteHost.exec_command no warnings on success"""

        mock_logger = MagicMock(name='LOG')
        common.remote_host.LOG.warn = mock_logger
        self.helper_remote_exec_command(command=['cowsay', 'Hello', 'World'])
        mock_logger.assert_not_called()

    def test_remote_exec_command_warning_on_falure(self):
        """Test RemoteHost.exec_command warning on failure"""

        mock_logger = MagicMock(name='LOG')
        common.remote_host.LOG.warn = mock_logger
        self.helper_remote_exec_command(return_value=1, exit_status=1)
        mock_logger.assert_called_once_with(ANY_IN_STRING('with exit status'), ANY, ANY, ANY)

    def helper_remote_exec_command_streams(self, out=None, err=None):
        """Test RemoteHost.exec_command steam out """

        with patch('paramiko.SSHClient') as mock_ssh:
            # Test a command as list
            remote = common.remote_host.RemoteHost('test_host', 'test_user', 'test_pem_file')

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

            remote._perform_exec = mock.MagicMock(name='_perform_exec')
            remote._perform_exec.return_value = 0

            remote.exec_command(
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

            if out is None:
                expected_out = common.remote_host.INFO_ADAPTER
            else:
                expected_out = out

            if err is None:
                expected_err = common.remote_host.WARN_ADAPTER
            else:
                expected_err = err

            remote._perform_exec.assert_called_once_with('command', expected_out, expected_err,
                                                         stdout, stderr, 'max_time_ms',
                                                         'no_output_timeout_ms')

    def test_remote_exec_command_default_streams(self):
        """ test remote exec uses the correct default info and err streams """
        self.helper_remote_exec_command_streams()

    def test_exec_mongo_warn(self):
        """ test remote exec uses the correct custom info and err streams """
        self.helper_remote_exec_command_streams(out=StringIO(), err=StringIO())

    def helper_remote_host_ssh_ex(self, exception=Exception()):
        """Test RemoteHost constructor ssh exception handling"""
        with patch('paramiko.SSHClient') as mock_paramiko:
            mock_ssh = MagicMock(name='connection')
            mock_paramiko.return_value = mock_ssh

            mock_ssh.connect.side_effect = exception
            common.remote_host.RemoteHost('test_host', 'test_user', 'test_pem_file')

    def test_remote_host_ssh_ex(self):
        """Test RemoteHost constructor ssh exception handling"""
        self.assertRaises(SystemExit, self.helper_remote_host_ssh_ex, paramiko.SSHException())

    def test_remote_host_sock_ex(self):
        """Test RemoteHost constructor socket exception handling"""
        self.assertRaises(SystemExit, self.helper_remote_host_ssh_ex, socket.error())

    def test_remote_host_ex(self):
        """Test RemoteHost constructor exception handling"""
        self.assertRaises(Exception, self.helper_remote_host_ssh_ex)


if __name__ == '__main__':
    unittest.main()
