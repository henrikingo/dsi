"""Provide abstraction over running commands on remote or local machines."""
from collections import MutableMapping, namedtuple
from functools import partial
import itertools
import logging
import os
import select
import shutil
import signal
import socket
from stat import S_ISDIR
import subprocess
import time

import paramiko

from common.log import IOLogAdapter
from thread_runner import run_threads

HostInfo = namedtuple('HostInfo', ['ip_or_name', 'category', 'offset'])

LOG = logging.getLogger(__name__)
INFO_ADAPTER = IOLogAdapter(LOG, logging.INFO)
ERROR_ADAPTER = IOLogAdapter(LOG, logging.ERROR)


# https://stackoverflow.com/questions/23064636/python-subprocess-popen-blocks-with-shell-and-pipe
def restore_signals():
    """ restore signals in the child process or the process block forever"""
    signals = ('SIGPIPE', 'SIGXFZ', 'SIGXFSZ')
    for sig in signals:
        if hasattr(signal, sig):
            signal.signal(getattr(signal, sig), signal.SIG_DFL)


def close_safely(stream):
    ''' close the stream
    :parameter object stream: the stream instance or None
    '''
    if stream is not None:
        stream.close()


def repo_root():
    ''' Return the path to the root of the DSI repo '''
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _run_host_command_map(target_host, command, current_test_id=None):
    ''' Run one command against a target host if the command is a mapping.

    :param Host target_host: The host to send the command to
    :param dict command: The command to execute
    '''
    for key, value in command.iteritems():
        if key == "upload_repo_files":
            for local_file, remote_file in value.iteritems():
                local_file = os.path.join(repo_root(), local_file)
                LOG.debug('Uploading file %s to %s', local_file, remote_file)
                target_host.upload_file(local_file, remote_file)
        elif key == "upload_files":
            for local_file, remote_file in value.iteritems():
                LOG.debug('Uploading file %s to %s', local_file, remote_file)
                target_host.upload_file(local_file, remote_file)
        elif key == "retrieve_files":
            for remote_file, local_file in value.iteritems():
                if current_test_id:
                    local_file = os.path.join('reports', target_host.alias, current_test_id,
                                              os.path.normpath(local_file))
                else:
                    local_file = os.path.join('reports', target_host.alias,
                                              os.path.normpath(local_file))

                LOG.debug('Retrieving file %s from %s', local_file, remote_file)
                target_host.retrieve_path(local_file, remote_file)
        elif key == "exec":
            LOG.debug('Executing command %s', value)
            target_host.run(value.split(' '))
        elif key == "exec_mongo_shell":
            LOG.debug('Executing command %s in mongo shell', value)
            connection_string = value.get('connection_string', "")
            target_host.exec_mongo_command(value['script'], connection_string=connection_string)
        else:
            raise UserWarning("Invalid command type")


def _run_host_command(host_list, command, config, current_test_id=None):
    '''For each host in the list, make a parallelized call to make_host_runner to make the
    appropriate host and run the set of commands

    :param list host_list: List of ip addresses to connect to
    :param str/dict command: The command to execute. If str, run that
    command. If dict, type is one of upload_repo_files, upload_files,
    retrieve_files, exec, or exec_mongo_shell
    :param ConfigDict config: The system configuration
    :param string current_test_id: Indicates the id for the test related to the current command. If
    there is not a specific test related to the current command, the value of current_test_id will
    be None.
    '''
    if not host_list:
        return

    LOG.debug('Calling run command for %s with command %s', str(host_list), str(command))
    ssh_user = config['infrastructure_provisioning']['tfvars']['ssh_user']
    ssh_key_file = config['infrastructure_provisioning']['tfvars']['ssh_key_file']
    ssh_key_file = os.path.expanduser(ssh_key_file)

    thread_commands = []
    for host_info in host_list:
        thread_commands.append(
            partial(make_host_runner, host_info, command, ssh_user, ssh_key_file, current_test_id))

    run_threads(thread_commands, daemon=True)


def make_host_runner(host_info, command, ssh_user, ssh_key_file, current_test_id=None):
    '''For the host, make an appropriate RemoteHost or
    LocalHost Object and run the set of commands

    :param namedtuple host_info: Public IP address or the string localhost, category
    and offset
    :param str ssh_user: The user id to use
    :param str ssh_key_file: The keyfile to use
    :param str/dict command: The command to execute. If str, run that
    command. If dict, type is one of upload_repo_files, upload_files,
    retrieve_files, exec, or exec_mongo_shell
    :param string current_test_id: Indicates the id for the test related to the current command. If
    there is not a specific test related to the current command, the value of current_test_id will
    be None.
    '''
    # Create the appropriate host type
    target_host = make_host(host_info, ssh_user, ssh_key_file)
    try:
        # If command is a string, pass it directly to run
        if isinstance(command, str):
            target_host.run(command)

        # If command is a dictionary, parse it
        elif isinstance(command, MutableMapping):
            _run_host_command_map(target_host, command, current_test_id)
    finally:
        target_host.close()


def make_host(host_info, ssh_user, ssh_key_file):
    '''
    Create a host object based off of host_ip_or_name. The code that receives the host is
    responsible for calling close on the host instance. Each RemoteHost instance can have 2*n+1 open
    sockets (where n is the number of exec_command calls with Pty=True) otherwise n is 1 so there
    is a max of 3 open sockets.

    :param namedtuple host_info: Public IP address or the string localhost, category
    and offset
    :param str ssh_user: The user id to use
    :param str ssh_key_file: The keyfile to use
    :rtype Host
    '''
    if host_info.ip_or_name in ['localhost', '127.0.0.1', '0.0.0.0']:
        LOG.debug("Making localhost for %s", host_info.ip_or_name)
        host = LocalHost()
    else:
        LOG.debug("Making remote host for %s", host_info.ip_or_name)
        host = RemoteHost(host_info.ip_or_name, ssh_user, ssh_key_file)
    host.alias = "{category}.{offset}".format(category=host_info.category, offset=host_info.offset)
    return host


def _extract_hosts(key, config):
    '''Extract a list of public IP addresses for hosts based off of the
    key. Valid keys are mongod, mongos, configsvr, and
    workload_client.

    :param str key: The key to use (mongod, mongod, ...)
    :param ConfigDict config: The configugration

    :returns  list of HostInfo objects
    '''
    if key in config['infrastructure_provisioning']['out']:
        return [
            HostInfo(host_info['public_ip'], key, i)
            for i, host_info in enumerate(config['infrastructure_provisioning']['out'][key])
        ]
    return list()


def extract_hosts(key, config):
    '''Extract a list of public IP addresses for hosts based off of the
    key. Valid keys are mongod, mongos, configsvr, workload_client, as
    well as the helpers all_hosts and all_servers
    '''

    if key == 'localhost':
        return [HostInfo('localhost', 'localhost', 0)]
    if key == 'all_servers':
        return list(
            itertools.chain.from_iterable(
                (_extract_hosts(key, config) for key in ['mongod', 'mongos', 'configsvr'])))
    if key == 'all_hosts':
        return list(
            itertools.chain.from_iterable(
                (_extract_hosts(key, config)
                 for key in ['mongod', 'mongos', 'configsvr', 'workload_client'])))
    return _extract_hosts(key, config)


def run_host_command(target, command, config, current_test_id=None):
    ''' Sets up and runs a command for use on the appropriate hosts
    :param string target: The target to run the command on.
    :param dict command: The action to run.
    :param dict(ConfigDict) config: The system configuration.
    :param string current_test_id: Indicates the id for the test related to the current command. If
    there is not a specific test related to the current command, the value of current_test_id will
    be None.
    '''

    assert target.startswith('on_')
    target = target[3:]
    hosts = extract_hosts(target, config)
    _run_host_command(hosts, command, config, current_test_id)


class Host(object):
    """Base class for hosts."""

    def __init__(self, host):
        self._alias = None
        self.host = host

    @property
    def alias(self):
        """ property getter

        :returns string the alias or the host if alias is not set
        """
        if not self._alias:
            return self.host
        return self._alias

    @alias.setter
    def alias(self, alias):
        self._alias = alias

    def exec_command(self, argv, out=None, err=None, pty=False):
        """Execute the command and log the output.
        :param string or list argv: the command to run.
        :param IO out: standard out from the command is written to this IO. If None is supplied
        then the INFO_ADAPTER will be used.
        :param IO err: standard err from the command is written to this IO on error. If None is
         supplied then the ERROR_ADAPTER will be used.
        :param bool pty: only valied for remote commands. if pty is set to True, then the shell
        command is executed in a pseudo terminal. As a result, the commands will be killed if the
        host is closed.
        """
        raise NotImplementedError()

    def run(self, argvs):
        """
        Runs a command or list of commands
        :param string or list argvs: The string to execute, or one argument vector or list of
        argv's [file, arg]
        """
        if not argvs or not isinstance(argvs, (list, basestring)):
            raise ValueError("Argument must be a nonempty list or string.")

        if isinstance(argvs, basestring):
            return self.exec_command(argvs) == 0

        if not isinstance(argvs[0], list):
            argvs = [argvs]

        return all(self.exec_command(argv) == 0 for argv in argvs)

    def exec_mongo_command(self,
                           script,
                           remote_file_name="script.js",
                           connection_string="localhost:27017"):
        """
        Executes script in the mongo on the
        connection string. Returns the status code of executing the script
        :param script: String containing javascript to be run
        :param remote_file_name: Name and path of file to create with script contents
        :param connection_string: Connection information of mongo instance to run script on
        """
        self.create_file(remote_file_name, script)
        self.run(['cat', remote_file_name])
        argv = ['bin/mongo', '--verbose', connection_string, remote_file_name]
        status_code = self.exec_command(argv)
        return status_code

    def kill_remote_procs(self, name):
        """Kills all processes on the remote host by name."""
        while self.run(['pgrep', name]):
            self.run(['pkill', '-9', name])
            time.sleep(1)

    def kill_mongo_procs(self):
        """Kills all mongo processes on the remote host."""
        self.kill_remote_procs('mongo')

    def create_file(self, remote_path, file_contents):
        """Creates a file on the remote host"""
        raise NotImplementedError()

    def upload_file(self, local_path, remote_path):
        """Copy a file to the host"""
        raise NotImplementedError()

    def retrieve_path(self, local_path, remote_path):
        """Retrieve a file from the host"""
        raise NotImplementedError()

    def close(self):
        """Cleanup any connections"""
        pass


class RemoteHost(Host):
    """Represents a SSH connection to a remote host."""

    def __init__(self, host, user, pem_file):
        super(RemoteHost, self).__init__(host)
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.client.AutoAddPolicy())
        LOG.debug('host: %s, user: %s, pem_file: %s', host, user, pem_file)
        try:
            ssh.connect(host, username=user, key_filename=pem_file)
            ftp = ssh.open_sftp()
        except (paramiko.SSHException, socket.error):
            LOG.exception('failed to connect to %s@%s', user, host)
            exit(1)
        self._ssh = ssh
        self.ftp = ftp
        self.user = user

    def exec_command(self, argv, out=None, err=None, pty=False):
        """Execute the argv command and log the output.
        :param string or list argv: the command to execute.
        :param bool pty: only valied for remote commands. if pty is set to True, then the shell
        command is executed in a pseudo terminal. As a result, the commands will be killed if the
        host is closed.
        :param IO out: standard out from the command is written to this IO. If None is supplied
        then the INFO_ADAPTER will be used.
        :param IO err: standard err from the command is written to this IO on error. If None is
         supplied then the ERROR_ADAPTER will be used.
        :returns int the exit status of the command.
        """
        # pylint: disable=too-many-branches
        if not argv or not isinstance(argv, (list, basestring)):
            raise ValueError("Argument must be a nonempty list or string.")

        if out is None:
            out = INFO_ADAPTER
        if err is None:
            err = ERROR_ADAPTER

        if isinstance(argv, list):
            command = ' '.join(argv)
        elif isinstance(argv, basestring):
            command = argv

        LOG.info('[%s@%s]$ %s', self.user, self.host, command)
        stdin = None
        stdout = None
        stderr = None
        exit_status = 1
        try:
            stdin, stdout, stderr = self._ssh.exec_command(command, get_pty=pty)
            stdin.channel.shutdown_write()
            stdin.close()
            # Stream the output of the command to the log
            while not stdout.channel.exit_status_ready():
                for line in stdout:
                    out.write(line)
            # Log the rest of stdout and stderr
            for line in stdout:
                out.write(line)
            exit_status = stdout.channel.recv_exit_status()
            if exit_status != 0:
                for line in stderr:
                    err.write(line)
                LOG.warn('%s \'%s\': Failed with exit status %s', self.alias, command, exit_status)
            stdout.close()
            stderr.close()
        except paramiko.SSHException:
            LOG.exception('failed to exec command on %s@%s', self.user, self.host)
        finally:
            close_safely(stdin)
            close_safely(stdout)
            close_safely(stderr)
        return exit_status

    def create_file(self, remote_path, file_contents):
        """Creates a file on the remote host"""
        with self.ftp.file(remote_path, 'w') as remote_file:
            remote_file.write(file_contents)
            remote_file.flush()

    def upload_file(self, local_path, remote_path):
        """Copy a file to the host"""
        self.ftp.put(local_path, remote_path)

        # Get standard permissions mask e.g. 0755
        source_permissions = os.stat(local_path).st_mode & 0777
        self.ftp.chmod(remote_path, source_permissions)

    def remote_exists(self, remote_path):
        """Test whether a remote path exists.  Returns False if it doesn't exist or on error

        :param str remote_path: the remote path
        """
        try:
            self.ftp.stat(remote_path)
        except (IOError, paramiko.SFTPError, os.error):
            return False
        return True

    def remote_isdir(self, remote_path):
        """Test whether a remote path exists and is a directory.  Returns False if it
        doesn't exist or on error

        :param str remote_path: the remote path
        """
        try:
            stat = self.ftp.stat(remote_path)
        except os.error:
            return False
        return S_ISDIR(stat.st_mode)

    def _retrieve_file(self, local_file, remote_file):
        """ retrieve a single remote file. The local directories will
        be created, if required.

        :param str local_file: the local filename. It must be a filename.
        :param str remote_file: the remote file location. It must be a filename.
        """
        LOG.debug("_retrieve_files: file '%s:%s' ", self.alias, remote_file)
        local_dir = os.path.dirname(local_file)
        local_dir = os.path.normpath(local_dir)
        if not os.path.exists(local_dir):
            os.makedirs(local_dir)
        self.ftp.get(remote_file, os.path.normpath(local_file))

    def retrieve_path(self, local_path, remote_path):
        """ retrieve a path from a remote server. If the remote_path is
        a directory, then the contents of the directory are downloaded
        recursively. If not then the single file will be downloaded to the local
        path.

        Any path elements in the local path will only be created if and when a file is
        downloaded. As a result, an empty directory tree will not be created locally.

        :param str local_path: the path (file or directory) to download to. This
        can contain relative paths, these paths will only be normalized at the last possible
        moment.
        :param str remote_path: the remote path, this can be a file or directory location. The
        path will be normalized immediately.
        """
        if not self.remote_exists(remote_path):
            LOG.debug("retrieve_files '%s:%s' does not exist.", self.alias, remote_path)
            return

        if self.remote_isdir(remote_path):
            LOG.debug("retrieve_files: directory '%s:%s'", self.alias, remote_path)

            for filename in self.ftp.listdir(remote_path):
                remote = os.path.join(remote_path, filename)

                local_file = os.path.join(local_path, filename)
                local_file = os.path.normpath(local_file)

                self.retrieve_path(local_file, remote)
        else:
            self._retrieve_file(local_path, remote_path)

    def close(self):
        """Close the ssh connection."""
        self._ssh.close()
        self.ftp.close()


def _stream_proc_logs(proc, out, err, timeout=.5):
    """ stream proc.stdout and proc.stderr to out and err
    :param proc: the sub process
    :param IO out: the proc.stdout stream destination.
    :param IO err: the proc.stderr stream destination.
    :param float timeout: wait for up to a max of this amount of seconds.
    """
    try:
        # stream standard out
        while True:

            ready, _, _ = select.select((proc.stdout, proc.stderr), (), (), timeout)

            if proc.stdout in ready:
                line = proc.stdout.readline()
                if line:
                    out.write(line)
                elif proc.returncode is not None:
                    # The program has exited, and we have read everything written to stdout
                    ready.remove(proc.stdout)

            if proc.stderr in ready:
                line = proc.stderr.readline()
                if line:
                    err.write(line)
                elif proc.returncode is not None:
                    # The program has exited, and we have read everything written to stderr
                    ready.remove(proc.stderr)

            if proc.poll() is not None and not ready:
                break
    # closed stream
    except ValueError:
        pass


class LocalHost(Host):
    """Represents a connection to the local host."""

    def __init__(self):
        super(LocalHost, self).__init__("localhost")

    def exec_command(self, argv, out=None, err=None, pty=False):
        """Execute the command and log the output.
        :type argv: string or list containing the command to execute
        :param IO out: standard out from the command is written to this IO. If None is supplied
        then the INFO_ADAPTER will be used.
        :param IO err: standard err from the command is written to this IO on error. If None is
         supplied then the ERROR_ADAPTER will be used.
        :param bool pty: only valied for remote commands. if pty is set to True, then the shell
        command is executed in a pseudo terminal. As a result, the commands will be killed if the
        host is closed.
        """
        if not argv or not isinstance(argv, (list, basestring)):
            raise ValueError("Argument must be a nonempty list or string.")
        if out is None:
            out = INFO_ADAPTER
        if err is None:
            err = ERROR_ADAPTER

        command = str(argv)
        if isinstance(argv, list):
            command = ' '.join(argv)

        LOG.info('[localhost]$ %s', command)
        proc = subprocess.Popen(
            ['bash', '-c', command],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=restore_signals)

        _stream_proc_logs(proc, out, err)

        if proc.returncode != 0:
            LOG.warn('%s \'%s\': Failed with exit status %s', self.alias, command,
                     proc.returncode)
        return proc.returncode

    def create_file(self, remote_path, file_contents):
        """Creates a file on the local host"""
        with open(remote_path, 'w') as local_file:
            local_file.write(file_contents)

    def upload_file(self, local_path, remote_path):
        """Copy a file to the host"""
        if local_path == remote_path:
            LOG.warning('Uploading file locally to same path. Skipping step')
        else:
            shutil.copyfile(local_path, remote_path)
            shutil.copymode(local_path, remote_path)

    def retrieve_path(self, local_path, remote_path):
        """Retrieve a file from the host"""
        if local_path == remote_path:
            LOG.warning('Retrieving file locally to same path. Skipping step')
        shutil.copyfile(remote_path, local_path)
