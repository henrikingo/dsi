"""
Provide abstraction over running commands on remote or local machines
"""

from collections import MutableMapping, namedtuple
from datetime import datetime
from functools import partial
import itertools
import logging
import os
import select
import shutil
import signal
import socket
import tempfile
from stat import S_ISDIR
import subprocess
import time

import paramiko

from common.utils import mkdir_p
from common.log import IOLogAdapter
import common.utils
from thread_runner import run_threads

ONE_SECOND_MILLIS = 1000.0
ONE_MINUTE_MILLIS = 60 * ONE_SECOND_MILLIS
TEN_MINUTE_MILLIS = 10 * ONE_MINUTE_MILLIS

HostInfo = namedtuple('HostInfo', ['ip_or_name', 'category', 'offset'])

LOG = logging.getLogger(__name__)
INFO_ADAPTER = IOLogAdapter(LOG, logging.INFO)
ERROR_ADAPTER = IOLogAdapter(LOG, logging.ERROR)


def setup_ssh_agent(config):
    """
    Setup the ssh-agent, and update our environment for it.

    :param ConfigDict config: The system configuration
    """
    ssh_agent_info = subprocess.check_output(['ssh-agent', '-s'])
    # This expansion updates our environment by parsing the info from the previous line. It splits
    # the data into lines, and then for any line of the form "key=value", adds {key: value} to the
    # environment.
    os.environ.update(dict([line.split('=') for line in ssh_agent_info.split(';') if '=' in line]))
    ssh_key_file = config['infrastructure_provisioning']['tfvars']['ssh_key_file']
    ssh_key_file = os.path.expanduser(ssh_key_file)
    subprocess.check_call(['ssh-add', ssh_key_file])


# https://stackoverflow.com/questions/23064636/python-subprocess-popen-blocks-with-shell-and-pipe
def restore_signals():
    """
    Restore signals in the child process or the process block forever
    """
    signals = ('SIGPIPE', 'SIGXFZ', 'SIGXFSZ')
    for sig in signals:
        if hasattr(signal, sig):
            signal.signal(getattr(signal, sig), signal.SIG_DFL)


def close_safely(stream):
    """
    Close the stream.

    :param object stream: The stream instance or None
    """
    if stream is not None:
        stream.close()


def _run_host_command_map(target_host, command, current_test_id=None):
    """
    Run one command against a target host if the command is a mapping.

    :param Host target_host: The host to send the command to
    :param dict command: The command to execute
    :param current_test_id: Indicates the id for the test related to the current command. If there
    is not a specific test related to the current command, the value of current_test_id will be
    None.
    :type current_test_id: str, None
    """
    # pylint: disable=too-many-branches
    for key, value in command.iteritems():
        if key == "upload_repo_files":
            for paths in value:
                source = os.path.join(common.utils.get_dsi_path(), paths['source'])
                target = paths['target']
                LOG.debug('Uploading file %s to %s', source, target)
                target_host.upload_file(source, target)
        elif key == "upload_files":
            for paths in value:
                LOG.debug('Uploading file %s to %s', paths['source'], paths['target'])
                target_host.upload_file(paths['source'], paths['target'])
        elif key == "retrieve_files":
            for paths in value:
                source = paths['source']
                target = paths['target']
                if current_test_id:
                    target = os.path.join('reports', target_host.alias, current_test_id,
                                          os.path.normpath(target))
                else:
                    target = os.path.join('reports', target_host.alias, os.path.normpath(target))

                LOG.debug('Retrieving file %s from %s', source, target)
                target_host.retrieve_path(source, target)
        elif key == "exec":
            LOG.debug('Executing command %s', value)
            target_host.run(value.split(' '))
        elif key == "exec_mongo_shell":
            LOG.debug('Executing command %s in mongo shell', value)
            connection_string = value.get('connection_string', "")
            target_host.exec_mongo_command(value['script'], connection_string=connection_string)
        elif key == "checkout_repos":
            for paths in value:
                source = paths['source']
                target = paths['target']
                branch = paths['branch'] if 'branch' in paths else None
                LOG.debug('Checking out git repository %s to %s', target, source)
                target_host.checkout_repos(source, target, str(branch))
        else:
            raise UserWarning("Invalid command type")


def _run_host_command(host_list, command, config, current_test_id=None):
    """
    For each host in the list, make a parallelized call to make_host_runner to make the appropriate
    host and run the set of commands.

    :param list host_list: List of ip addresses to connect to
    :param command: The command to execute. If str, run that command. If dict, type is one of
    upload_repo_files, upload_files, retrieve_files, exec, or exec_mongo_shell.
    :type command: str, dict
    :param ConfigDict config: The system configuration
    :param current_test_id: Indicates the id for the test related to the current command. If there
    is not a specific test related to the current command, the value of current_test_id will be
    None.
    :type current_test_id: str, None
    """
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
    """
    For the host, make an appropriate RemoteHost or LocalHost Object and run the set of commands.

    :param namedtuple host_info: Public IP address or the string localhost, category and offset
    :param str ssh_user: The user id to use
    :param str ssh_key_file: The keyfile to use
    :param command: The command to execute. If str, run that command. If dict, type is one of
    upload_repo_files, upload_files, retrieve_files, exec, or exec_mongo_shell.
    :type command: str, dict
    :param current_test_id: Indicates the id for the test related to the current command. If there
    is not a specific test related to the current command, the value of current_test_id will be
    None.
    :type current_test_id: str, None
    """
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
    """
    Create a host object based off of host_ip_or_name. The code that receives the host is
    responsible for calling close on the host instance. Each RemoteHost instance can have 2*n+1 open
    sockets (where n is the number of exec_command calls with Pty=True) otherwise n is 1 so there is
    a max of 3 open sockets.

    :param namedtuple host_info: Public IP address or the string localhost, category and offset
    :param str ssh_user: The user id to use
    :param str ssh_key_file: The keyfile to use
    :rtype: Host
    """
    if host_info.ip_or_name in ['localhost', '127.0.0.1', '0.0.0.0']:
        LOG.debug("Making localhost for %s", host_info.ip_or_name)
        host = LocalHost()
    else:
        LOG.debug("Making remote host for %s", host_info.ip_or_name)
        host = RemoteHost(host_info.ip_or_name, ssh_user, ssh_key_file)
    host.alias = "{category}.{offset}".format(category=host_info.category, offset=host_info.offset)
    return host


def _extract_hosts(key, config):
    """
    Extract a list of public IP addresses for hosts based off of the key. Valid keys are mongod,
    mongos, configsvr, and workload_client.

    :param str key: The key to use (mongod, mongod, ...)
    :param ConfigDict config: The system configuration
    :rtype: list of HostInfo objects
    """
    if key in config['infrastructure_provisioning']['out']:
        return [
            HostInfo(host_info['public_ip'], key, i)
            for i, host_info in enumerate(config['infrastructure_provisioning']['out'][key])
        ]
    return list()


def make_workload_runner_host(config):
    """
    Convenience function to make a host to connect to the workload runner node.

    :param ConfigDict config: The system configuration
    """
    ssh_key_file = config['infrastructure_provisioning']['tfvars']['ssh_key_file']
    ssh_key_file = os.path.expanduser(ssh_key_file)
    ssh_user = config['infrastructure_provisioning']['tfvars']['ssh_user']
    host_info = extract_hosts('workload_client', config)[0]
    return make_host(host_info, ssh_user, ssh_key_file)


def extract_hosts(key, config):
    """
    Extract a list of public IP addresses for hosts based off of the key. Valid keys are mongod,
    mongos, configsvr, workload_client, as well as the helpers all_hosts and all_servers.

    :param ConfigDict config: The system configuration
    """

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
    """
    Sets up and runs a command for use on the appropriate hosts.

    :param str target: The target to run the command on
    :param dict command: The action to run
    :param ConfigDict config: The system configuration
    :param current_test_id: Indicates the id for the test related to the current command. If there
    is not a specific test related to the current command, the value of current_test_id will be
    None.
    :type current_test_id: str, None
    """

    assert isinstance(command, MutableMapping), "command isn't a dict"
    assert target.startswith('on_')

    keys = command.keys()
    target = target[3:]
    hosts = extract_hosts(target, config)
    LOG.info("Running command(s) %s on %s", keys, target)
    _run_host_command(hosts, command, config, current_test_id)
    LOG.debug("Done running command(s) %s on %s", keys, target)


def run_host_commands(commands, config, current_test_id=None):
    """
    Plural version of run_host_command: run a list of commands.

    Example of commands:

    [
        { 'on_workload_client': { 'upload_files': [{ 'source': 'path', 'target': 'dest' }] } }
    ]

    :param list commands: List of dict actions to run
    :param ConfigDict config: The system configuration
    :param current_test_id: Indicates the id for the test related to the current command. If there
    is not a specific test related to the current command, the value of current_test_id will be
    None.
    :type current_test_id: str, None
    """
    for command in commands:
        # Item should be a map with one entry
        assert isinstance(command, MutableMapping), "command in list isn't a dict"
        assert len(command.keys()) == 1, "command has more than one entry"
        for target, target_command in command.iteritems():
            target = command.keys()[0]
            run_host_command(target, target_command, config, current_test_id)


def never_timeout():
    """
    Function that never times out
    """
    return False


def check_timed_out(start, max_time_ms):
    """
    Check if max time ms has passed.

    :param datetime start: The start time
    :param max_time_ms: The max allowable time to run for or None for no timeout
    :type max_time_ms: int, float, None
    """
    delta = (datetime.now() - start).total_seconds() * ONE_SECOND_MILLIS
    return delta > max_time_ms


def create_timer(start, max_time_ms):
    """
    Create a watchdog timeout function.

    :param datetime start: The start time
    :param max_time_ms: The time limit in milliseconds for processing this operation, defaults to
    None (no timeout)
    :type max_time_ms: int, float, None
    :rtype: function that returns True when max_time_ms has elapsed
    """
    if max_time_ms is None:
        is_timed_out = never_timeout
    else:
        is_timed_out = partial(check_timed_out, start, max_time_ms)
    return is_timed_out


class Host(object):
    """
    Base class for hosts
    """

    def __init__(self, host):
        self._alias = None
        self.host = host

    @property
    def alias(self):
        """
        Property getter.

        :rtype: The alias or the host if alias is not set
        """
        if not self._alias:
            return self.host
        return self._alias

    @alias.setter
    def alias(self, alias):
        self._alias = alias

    # pylint: disable=too-many-arguments
    def exec_command(self,
                     argv,
                     stdout=None,
                     stderr=None,
                     get_pty=False,
                     max_time_ms=None,
                     no_output_timeout_ms=None):
        """
        Execute the command and log the output.

        :param argv: The command to run
        :type argv: str, list
        :param IO stdout: Standard out from the command is written to this IO. If None is supplied
        then the INFO_ADAPTER will be used.
        :param IO stderr: Standard err from the command is written to this IO on error. If None is
        supplied then the ERROR_ADAPTER will be used.
        :param bool get_pty: Only valid for remote commands. If pty is set to True, then the shell
        command is executed in a pseudo terminal. As a result, the commands will be killed if the
        host is closed.
        :param max_time_ms: the time limit in milliseconds for processing this operation.
                            Defaults to None (no timeout).
        :type max_time_ms: int, float or None.
        :param no_output_timeout_ms: the amount of time the command is allowed to go without
        any output on stdout. Not all host implementations support this - namely only
        RemoteHost at the moment
        :type no_output_timeout_ms: int, float, or None
        """
        raise NotImplementedError()

    def run(self, argvs):
        """
        Runs a command or list of commands.

        :param argvs: The string to execute, or one argument vector or list of argv's [file, arg]
        :type argvs: str, list
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
                           connection_string="localhost:27017",
                           max_time_ms=None):
        """
        Executes script in the mongo on the connection string. Returns the status code of executing
        the script.

        :param str script: The javascript to be run
        :param str remote_file_name: Name and path of file to create with script contents
        :param str connection_string: Connection information of mongo instance to run script on
        :param max_time_ms: The time limit in milliseconds for processing this operations, defaults
        to None (no timeout)
        :type max_time_ms: int, float, None
        """
        self.create_file(remote_file_name, script)
        self.run(['cat', remote_file_name])
        argv = ['bin/mongo', '--verbose', connection_string, remote_file_name]
        status_code = self.exec_command(argv, max_time_ms=max_time_ms)
        return status_code

    def kill_remote_procs(self,
                          name,
                          signal_number=signal.SIGKILL,
                          delay_ms=ONE_SECOND_MILLIS,
                          max_time_ms=TEN_MINUTE_MILLIS):
        """
        Kills all processes on the host matching name pattern.

        :param str name: The process name pattern. This pattern only matches on the process name.
        :param int signal_number: The signal to send, defaults to SIGKILL(9). It should be a valid
        signal.
        :param delay_ms: The milliseconds to sleep for before checking if the processes valid
        shutdown. Defaults to 1 second (in millis), it should be greater than 0.
        :type delay_ms: int, float
        :param max_time_ms: The time limit in milliseconds for processing this operation, defaults
        to None (no timeout)
        :type max_time_ms: int, float, None
        """
        signal_number = '-' + str(signal_number)
        delay_seconds = delay_ms / ONE_SECOND_MILLIS
        if max_time_ms == 0:
            max_time_ms = delay_ms

        is_timed_out = create_timer(datetime.now(), max_time_ms)

        while not is_timed_out():
            self.run(['pkill', signal_number, name])
            if not self.run(['pgrep', name]):
                return True
            time.sleep(delay_seconds)

        return False

    def kill_mongo_procs(self, signal_number=signal.SIGKILL, max_time_ms=30 * ONE_SECOND_MILLIS):
        """
        Kills all processes matching the patterm 'mongo' (includes 'mongo', 'mongos', 'mongod') on
        the host by sending signal_number every second until there are no matching processes or the
        timeout has elapsed.

        :param int signal_number: The signal to send, defaults to SIGKILL(9). It must be greater
        than 0 and a valid signal.
        :param max_time_ms: The time limit in milliseconds for processing this operation, defaults
        to None (no timeout)
        :type max_time_ms: int, float, None
        """
        return self.kill_remote_procs('mongo', signal_number, max_time_ms=max_time_ms)

    def create_file(self, remote_path, file_contents):
        """
        Creates a file on the remote host
        """
        raise NotImplementedError()

    # Note: Try to keep arguments for all these methods in a (source, destination) order
    def upload_file(self, local_path, remote_path):
        """
        Copy a file to the host
        """
        raise NotImplementedError()

    def retrieve_path(self, remote_path, local_path):
        """
        Retrieve a file from the host
        """
        raise NotImplementedError()

    def checkout_repos(self, source, target, branch=None):
        """
        Clone repository from GitHub into target directory.

        :param str source: Link to GitHub repository
        :param str target: Path to target directory
        :param branch: Specific branch to clone, if None clones default branch.
        :types branch: str, None
        """
        if not os.path.isdir(target):
            LOG.info('checkout_repos target directory %s does not exist', target)
            mkdir_p(os.path.dirname(target))
            self.exec_command(['git', 'clone', source, target])
            if branch is not None:
                self.exec_command(['cd', target, '&&', 'git', 'checkout', branch])
        elif self.exec_command(['cd', target, '&&', 'git', 'status']) != 0:
            raise UserWarning('%s exists and is not a git repository', target)
        else:
            LOG.info('checkout_repos target directory %s exists and is a git repository', target)

    def close(self):
        """
        Cleanup any connections
        """
        pass


def _stream(source, destination):
    """
    Stream lines from source to destination. Silently hand socket.timeouts.

    :param IO source: Reads lines from this stream
    :param IO destination: Writes lines to this stream
    """
    any_lines = False
    try:
        for line in source:
            destination.write(line)
            any_lines = True
    except socket.timeout:
        pass
    return any_lines


def _connected_ssh(host, user, pem_file):
    """
    Create a connected paramiko ssh client and ftp connection
    or raise if cannot connect
    :param host: hostname to connect to
    :param user: username to use
    :param pem_file: ssh pem file for connection
    :return: paramiko (SSHClient, SFTPClient) tuple
    """
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.client.AutoAddPolicy())
    try:
        ssh.connect(host, username=user, key_filename=pem_file)
        ftp = ssh.open_sftp()
        # Setup authentication forwarding. See
        # https://stackoverflow.com/questions/23666600/ssh-key-forwarding-using-python-paramiko
        session = ssh.get_transport().open_session()
        paramiko.agent.AgentRequestHandler(session)
    except (paramiko.SSHException, socket.error) as err:
        LOG.exception('failed to connect to %s@%s', user, host)
        raise err
    return ssh, ftp


class RemoteHost(Host):
    """
    Represents a SSH connection to a remote host
    """

    def __init__(self, host, user, pem_file):
        """
        :param host: hostname
        :param user: username
        :param pem_file: ssh pem file
        """
        super(RemoteHost, self).__init__(host)
        LOG.debug('host: %s, user: %s, pem_file: %s', host, user, pem_file)
        try:
            ssh, ftp = _connected_ssh(host, user, pem_file)
            self._ssh = ssh
            self.ftp = ftp
            self.user = user
        except (paramiko.SSHException, socket.error):
            exit(1)

    # pylint: disable=too-many-arguments
    # pylint: disable=too-many-locals
    def exec_command(self,
                     argv,
                     stdout=None,
                     stderr=None,
                     get_pty=False,
                     max_time_ms=None,
                     no_output_timeout_ms=None):
        """
        Execute the argv command on the remote host and log the output.

        For parameters/returns, see :method: `Host.exec_command`.
        """
        # pylint: disable=too-many-branches
        if not argv or not isinstance(argv, (list, basestring)):
            raise ValueError("Argument must be a nonempty list or string.")

        if (max_time_ms is not None and no_output_timeout_ms is not None
                and no_output_timeout_ms > max_time_ms):
            LOG.warn("Can't wait %s ms for output when max time is %s ms", no_output_timeout_ms,
                     max_time_ms)

        if stdout is None:
            stdout = INFO_ADAPTER
        if stderr is None:
            stderr = ERROR_ADAPTER

        if isinstance(argv, list):
            command = ' '.join(argv)
        else:
            command = argv

        LOG.info('[%s@%s]$ %s', self.user, self.host, command)

        # scoping
        ssh_stdin, ssh_stdout, ssh_stderr = None, None, None
        exit_status, did_timeout, time_taken_seconds = None, None, None

        try:
            ssh_stdin, ssh_stdout, ssh_stderr = self._ssh.exec_command(command, get_pty=get_pty)
            ssh_stdin.channel.shutdown_write()
            ssh_stdin.close()

            exit_status, did_timeout, time_taken_seconds = self._perform_exec(
                stdout, stderr, ssh_stdout, ssh_stderr, no_output_timeout_ms, max_time_ms)

            ssh_stdout.close()
            ssh_stderr.close()
        except paramiko.SSHException:
            LOG.exception('failed to exec command on %s@%s', self.user, self.host)
        finally:
            close_safely(ssh_stdin)
            close_safely(ssh_stdout)
            close_safely(ssh_stderr)

        if did_timeout:
            LOG.warn('%s \'%s\': Timeout after %f seconds with exit status %s', self.alias, command,
                     time_taken_seconds, exit_status)
        elif exit_status != 0:
            LOG.warn('%s \'%s\': Failed after %f seconds with exit status %s', self.alias, command,
                     time_taken_seconds, exit_status)

        return exit_status

    # pylint: disable=no-self-use
    def _perform_exec(self, stdout, stderr, ssh_stdout, ssh_stderr, no_output_timeout_ms,
                      max_time_ms):
        """
        :return: tuple with (exit_status int, did_timeout bool, time_taken_seconds float)
        """
        total_operation_start = datetime.now()
        total_operation_is_timed_out = create_timer(total_operation_start, max_time_ms)
        no_output_timed_out = create_timer(datetime.now(), no_output_timeout_ms)

        # The channel settimeout causes reads to throw 'socket.timeout' if data does not arrive
        # within that time. This is not necessarily an error, it allows us to implement
        # max time ms without having to resort to threading.
        ssh_stdout.channel.settimeout(0.1)

        # Stream the output of the command to the log
        while (not total_operation_is_timed_out() and not no_output_timed_out()
               and not ssh_stdout.channel.exit_status_ready()):
            any_lines = _stream(ssh_stdout, stdout)
            if any_lines:
                no_output_timed_out = create_timer(datetime.now(), no_output_timeout_ms)

        # At this point we have either timed out or the command has finished. The code makes
        # a best effort to stream any remaining logs but the 'for line in ..' calls will
        # only block once for a max of 100 millis.
        #
        # Log the rest of stdout and stderr
        _stream(ssh_stdout, stdout)
        _stream(ssh_stderr, stderr)

        if ssh_stdout.channel.exit_status_ready():
            exit_status = ssh_stdout.channel.recv_exit_status()
            did_timeout = False
        else:
            exit_status = 1
            did_timeout = True

        time_taken_seconds = (datetime.now() - total_operation_start).total_seconds()
        return exit_status, did_timeout, time_taken_seconds

    def create_file(self, remote_path, file_contents):
        """
        Creates a file on the remote host
        """
        with self.ftp.file(remote_path, 'w') as remote_file:
            remote_file.write(file_contents)
            remote_file.flush()

    def upload_file(self, local_path, remote_path):
        """
        Copy a file or directory to the host.
        Uploading large files or a directory with lots of files may be slow as we don't do any
        compression.
        """
        if os.path.isdir(local_path):
            self._upload_dir(local_path, remote_path)
        else:
            self._upload_single_file(local_path, remote_path)

    def _upload_dir(self, local_path, remote_path):
        """
        Upload a directory, local->remote.
        Internally works by creating a tarball and uploading and unpacking that.

        :param local_path: Local directory to upload
        :param remote_path: Destination directory. Must already exist.
        """
        temp_dir = tempfile.mkdtemp()
        try:
            self.__upload_dir_unsafe(local_path, remote_path, temp_dir)
        finally:
            shutil.rmtree(temp_dir)

    def __upload_dir_unsafe(self, local_path, remote_path, temp_dir):
        """
        Upload a directory, local->remote, using a temporary tarball to store an intermediary
        tarball. If any exceptions during tar-ing or uploading, this won't clean up the temporary
        directory.

        :param local_path: Local directory to upload
        :param remote_path: Destination directory. Must already exist.
        :param temp_dir: Temporary directory to store intermediary tarball
        """
        tarball_name = '{}.tar'.format(os.path.basename(remote_path))
        remote_parent_dir = os.path.dirname(remote_path)
        remote_tarball_path = os.path.join(remote_parent_dir, tarball_name)

        tarball_path = shutil.make_archive(
            os.path.join(temp_dir, tarball_name), 'tar', local_path, '.')

        # Make way and upload it
        self.exec_command(['mkdir', '-p', remote_path])
        self._upload_single_file(tarball_path, remote_tarball_path)

        # Untar it. Have to rely on shell because tarfile doesn't operate remotely.
        self.exec_command(['tar', 'xf', remote_tarball_path, '-C', remote_path])

        # Cleanup remote
        self.exec_command(['rm', remote_tarball_path])

    def _upload_single_file(self, local_path, remote_path):
        """
        Upload single file, local->remote. Must be a single file (not a directory). For type-aware
        transfer, see upload_file.

        :param local_path: Local file to upload
        :param remote_path: Local file destination
        """
        self.ftp.put(local_path, remote_path)

        # Get standard permissions mask e.g. 0755
        source_permissions = os.stat(local_path).st_mode & 0777
        self.ftp.chmod(remote_path, source_permissions)

    def remote_exists(self, remote_path):
        """
        Test whether a remote path exists, returns False if it doesn't exist or on error.

        :param str remote_path: The remote path
        """
        try:
            self.ftp.stat(remote_path)
        except (IOError, paramiko.SFTPError, os.error):
            return False
        return True

    def remote_isdir(self, remote_path):
        """
        Test whether a remote path exists and is a directory, returns False if it doesn't exist or
        on error.

        :param str remote_path: The remote path
        """
        try:
            stat = self.ftp.stat(remote_path)
        except os.error:
            return False
        return S_ISDIR(stat.st_mode)

    def _retrieve_file(self, remote_file, local_file):
        """
        Retrieve a single remote file. The local directories will be created, if required.

        :param str local_file: The local filename, it must be a filename.
        :param str remote_file: The remote file location, it must be a filename.
        """
        LOG.debug("_retrieve_files: file '%s:%s' ", self.alias, remote_file)
        local_dir = os.path.dirname(local_file)
        local_dir = os.path.normpath(local_dir)
        if not os.path.exists(local_dir):
            os.makedirs(local_dir)
        self.ftp.get(remote_file, os.path.normpath(local_file))

    def retrieve_path(self, remote_path, local_path):
        """
        Retrieve a path from a remote server. If the remote_path is a directory, then the contents
        of the directory are downloaded recursively. If not then the single file will be downloaded
        to the local path.

        Any path elements in the local path will only be created if and when a file is downloaded.
        As a result, an empty directory tree will not be created locally.

        :param str local_path: The path (file or directory) to download to. This can contain
        relative paths, these paths will only be normalized at the last possible moment.
        :param str remote_path: The remote path, this can be a file or directory location. The path
        will be normalized immediately.
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

                self.retrieve_path(remote, local_file)
        else:
            self._retrieve_file(remote_path, local_path)

    def close(self):
        """
        Close the ssh connection
        """
        self._ssh.close()
        self.ftp.close()


# pylint: disable=too-many-arguments
def _stream_proc_logs(proc, out, err, is_timedout, timeout_s=.5):
    """
    Stream proc.stdout and proc.stderr to out and err.

    :param subprocess proc: The process to stream the logs for
    :param IO out: The proc.stdout stream destination
    :param IO err: The proc.stderr stream destination
    :param function is_timedout: Determine if the max allowable amount of time has elapsed
    :param float timeout_s: Select waits for up to a max of this amount of seconds
    """
    try:
        # Stream standard out
        while True:
            if is_timedout():
                return False
            ready, _, _ = select.select((proc.stdout, proc.stderr), (), (), timeout_s)

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
    # Closed stream
    except ValueError:
        pass
    return True


class LocalHost(Host):
    """
    Represents a connection to the local host
    """

    def __init__(self):
        super(LocalHost, self).__init__("localhost")

    # pylint: disable=too-many-arguments
    def exec_command(self,
                     argv,
                     stdout=None,
                     stderr=None,
                     get_pty=False,
                     max_time_ms=None,
                     no_output_timeout_ms=None):
        """
        Execute the command on the local host and log the output.

        For parameters/returns, see :method: `Host.exec_command`.
        """
        if no_output_timeout_ms is not None:
            LOG.error("no_output_timeout_ms %s not supported on LocalHost", no_output_timeout_ms)
        if not argv or not isinstance(argv, (list, basestring)):
            raise ValueError("Argument must be a nonempty list or string.")
        if stdout is None:
            stdout = INFO_ADAPTER
        if stderr is None:
            stderr = ERROR_ADAPTER

        command = str(argv)
        if isinstance(argv, list):
            command = ' '.join(argv)

        start = datetime.now()
        LOG.info('[localhost]$ %s', command)
        proc = subprocess.Popen(
            ['bash', '-c', command],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=restore_signals)
        is_timed_out = create_timer(start, max_time_ms)
        if _stream_proc_logs(proc, stdout, stderr, is_timed_out):
            exit_status = proc.returncode
            if exit_status != 0:
                LOG.warn('%s \'%s\': Failed with exit status %s', self.alias, command, exit_status)
        else:
            exit_status = 1
            LOG.warn('%s \'%s\': Timeout after %f seconds with exit status %s', self.alias, command,
                     (datetime.now() - start).total_seconds(), exit_status)
        return exit_status

    def create_file(self, remote_path, file_contents):
        """
        Creates a file on the local host
        """
        with open(remote_path, 'w') as local_file:
            local_file.write(file_contents)

    def upload_file(self, local_path, remote_path):
        """
        Copy a file to the host
        """
        if local_path == remote_path:
            LOG.warning('Uploading file locally to same path. Skipping step')
        else:
            shutil.copyfile(local_path, remote_path)
            shutil.copymode(local_path, remote_path)

    def retrieve_path(self, remote_path, local_path):
        """
        Retrieve a file from the host
        """
        if local_path == remote_path:
            LOG.warning('Retrieving file locally to same path. Skipping step')
        shutil.copyfile(remote_path, local_path)
