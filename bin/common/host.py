"""Provide abstraction over running commands on remote or local machines."""
import logging
import socket
import subprocess
import time

import paramiko


LOG = logging.getLogger(__name__)


def log_lines(level, lines):
    """Logs a list of lines without trailing whitespace"""
    for line in lines:
        if line:
            LOG.log(level, line.rstrip())

# pylint: disable=unused-argument
def run_commands(host_list, command, config):
    '''For each host in the list, make an appropriate RemoteHost or
    LocalHost Object and run the set of commands

    :param list host_list: List of ip addresses to connect to
    :param map command: The command to execute. The key is the type.
    :param ConfigDict config: The system configuration
    '''

    # Base code in mongodb_setup.py wrapping of host objects
    raise NotImplementedError

def execute_list(list_actions, config):
    '''
    Execute a list of actions on the appropriate hosts
    '''

    for item in list_actions:
        # Item should be a map with one entry
        assert isinstance(item, dict), 'item in list isn\'t a dict'
        assert len(item.keys()) == 1, 'item has more than one entry'
        for key, value in item.iteritems():
            if key == 'on_workload_client':
                clients = [client.public_ip for client in
                           config['infrastructure_provisioning']['out']['workload_client']]
                run_commands(clients, value, config)
            elif key == 'on_workload_client_shell':
                pass
            elif key == 'on_mongos':
                # This next line and ones like it can be pulled out into a simple helper
                mongoses = [mongos.public_ip for mongos in
                            config['infrastructure_provisioning']['out']['mongos']]
                run_commands(mongoses, value, config)
            elif key == 'on_mongod':
                pass
            elif key == 'on_configsvr':
                pass
            elif key == 'on_all_hosts':
                pass
            else:
                LOG.error("Unknown key %s in action list", key)

    raise NotImplementedError


class Host(object):
    """Base class for hosts."""

    def exec_command(self, argv):
        """Execute the command and log the output."""
        raise NotImplementedError()

    def run(self, argvs):
        """
        Runs a command or list of commands
        :param argvs: Argument vector or list of argv's [file, args, ...]
        """
        if not isinstance(argvs[0], list):
            argvs = [argvs]

        return all(self.exec_command(argv) == 0 for argv in argvs)

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

    def close(self):
        """Cleanup any connections"""
        pass


class RemoteHost(Host):
    """Represents a SSH connection to a remote host."""

    def __init__(self, host, user, pem_file):
        super(RemoteHost, self).__init__()
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.client.AutoAddPolicy())
        try:
            ssh.connect(host, username=user, key_filename=pem_file)
            ftp = ssh.open_sftp()
        except (paramiko.SSHException, socket.error):
            LOG.exception('failed to connect to %s@%s', user, host)
            exit(1)
        self._ssh = ssh
        self.ftp = ftp
        self.host = host
        self.user = user

    def exec_command(self, argv):
        """Execute the command and log the output."""
        command = ' '.join(argv)
        LOG.info('[%s@%s]$ %s', self.user, self.host, command)
        try:
            stdin, stdout, stderr = self._ssh.exec_command(command)
        except paramiko.SSHException:
            LOG.exception('failed to exec command on %s@%s',
                          self.user, self.host)
            return 1
        stdin.channel.shutdown_write()
        stdin.close()
        # Stream the output of the command to the log
        while not stdout.channel.exit_status_ready():
            log_lines(logging.INFO, [stdout.readline()])
        # Log the rest of stdout and stderr
        log_lines(logging.INFO, stdout.readlines())
        exit_status = stdout.channel.recv_exit_status()
        if exit_status != 0:
            log_lines(logging.ERROR, stderr.readlines())
            LOG.warn('Failed with exit status %s', exit_status)
        stdout.close()
        stderr.close()
        return exit_status

    def create_file(self, remote_path, file_contents):
        """Creates a file on the remote host"""
        with self.ftp.file(remote_path, 'w') as remote_file:
            remote_file.write(file_contents)
            remote_file.flush()

    def close(self):
        """Close the ssh connection."""
        self._ssh.close()
        self.ftp.close()


class LocalHost(Host):
    """Represents a connection to the local host."""

    def __init__(self):
        super(LocalHost, self).__init__()
        self.host = "localhost"

    def exec_command(self, argv):
        """Execute the command and log the output."""
        LOG.info('[localhost]$ %s', ' '.join(argv))
        proc = subprocess.Popen(
            ['bash', '-c', ' '.join(argv)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        for line in iter(proc.stdout.readline, b''):
            LOG.info(line.rstrip())
        # wait for the process to terminate
        proc.communicate()
        if proc.returncode != 0:
            LOG.warn('failed with exit status %s', proc.returncode)
        return proc.returncode

    def create_file(self, file_path, file_contents):
        """Creates a file on the local host"""
        with open(file_path, 'w') as local_file:
            local_file.write(file_contents)
