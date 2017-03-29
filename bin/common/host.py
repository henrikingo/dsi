"""Provide abstraction over running commands on remote or local machines."""
from collections import MutableMapping
import itertools
import logging
import os
import shutil
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

def repo_root():
    ''' Return the path to the root of the DSI repo '''
    return os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))))

def _run_command_map(target_host, command):
    ''' Run one command against a target host if the command is a mapping.

    :param Host target_host: The host to send the command to
    :param dict command: The command to execute
    '''
    for key, value in command.iteritems():
        if key == "upload_repo_files":
            for local_file, remote_file in value.iteritems():
                local_file = os.path.join(repo_root(),
                                          local_file)
                LOG.debug('Uploading file %s to %s', local_file, remote_file)
                target_host.upload_file(local_file, remote_file)
        elif key == "upload_files":
            for local_file, remote_file in value.iteritems():
                LOG.debug('Uploading file %s to %s', local_file, remote_file)
                target_host.upload_file(local_file, remote_file)
        elif key == "retrieve_files":
            for remote_file, local_file in value.iteritems():
                LOG.debug('Retrieving file %s from %s', local_file, remote_file)
                target_host.retrieve_file(local_file, remote_file)
        elif key == "exec":
            LOG.debug('Executing command %s', value)
            target_host.run(value.split(' '))
        elif key == "exec_mongo_shell":
            LOG.debug('Executing command %s in mongo shell', value)
            remote_file_name = 'script.js'
            target_host.create_file(remote_file_name, value['script'])
            connection_string = value.get('connection_string', "")
            command_list = ['bin/mongo', connection_string, remote_file_name]
            target_host.run(command_list)
        else:
            raise Exception("Invalid command type")

def run_command(host_list, command, config):
    '''For each host in the list, make an appropriate RemoteHost or
    LocalHost Object and run the set of commands

    :param list host_list: List of ip addresses to connect to
    :param str/dict command: The command to execute. If str, run that
    command. If dict, type is one of upload_repo_files, upload_files,
    retrieve_files, exec, or exec_mongo_shell
    :param ConfigDict config: The system configuration

    '''

    LOG.debug('Calling run command for %s with command %s', str(host_list), str(command))
    ssh_user = config['infrastructure_provisioning']['tfvars']['ssh_user']
    ssh_key_file = config['infrastructure_provisioning']['tfvars']['ssh_key_file']

    # If performance becomes a concern, we can operate on all hosts in
    # parallel
    for host_name in host_list:
        # Create the appropriate host type
        target_host = make_host(host_name, ssh_user, ssh_key_file)

        # If command is a string, pass it directly to run
        if isinstance(command, str):
            target_host.run(command)

        # If command is a dictionary, parse it
        elif isinstance(command, MutableMapping):
            _run_command_map(target_host, command)

def make_host(host_ip_or_name, ssh_user, ssh_key_file):
    '''
    Create a host object based off of host_ip_or_name.

    :param str host_ip_or_name: Public IP address or the string localhost
    :param str ssh_user: The user id to use
    :param str ssh_key_file: The keyfile to use
    :rtype Host
    '''
    if host_ip_or_name in ['localhost', '127.0.0.1', '0.0.0.0']:
        LOG.debug("Making localhost for %s", host_ip_or_name)
        return LocalHost()
    else:
        LOG.debug("Making remote host for %s", host_ip_or_name)
        return RemoteHost(host_ip_or_name, ssh_user, ssh_key_file)

def _extract_hosts(key, config):
    '''Extract a list of public IP addresses for hosts based off of the
    key. Valid keys are mongod, mongos, configsvr, and
    workload_client.

    :param str key: The key to use (mongod, mongod, ...)
    :param ConfigDict config: The configugration
    '''
    return [host_info['public_ip'] for host_info in
            config['infrastructure_provisioning']['out'][key]]

def extract_hosts(key, config):
    '''Extract a list of public IP addresses for hosts based off of the
    key. Valid keys are mongod, mongos, configsvr, workload_client, as
    well as the helpers all_hosts and all_servers
    '''

    if key == 'localhost':
        return ['localhost']
    if key == 'all_servers':
        return list(itertools.chain.from_iterable((_extract_hosts(key, config) for
                                                   key in ['mongod', 'mongos', 'configsvr'])))
    if key == 'all_hosts':
        return list(itertools.chain.from_iterable((_extract_hosts(key, config) for key in
                                                   ['mongod', 'mongos', 'configsvr',
                                                    'workload_client'])))
    return _extract_hosts(key, config)

def execute_list(list_actions, config):
    '''
    Execute a list of actions on the appropriate hosts
    '''

    for item in list_actions:
        # Item should be a map with one entry
        assert isinstance(item, MutableMapping), 'item in list isn\'t a dict'
        assert len(item.keys()) == 1, 'item has more than one entry'
        for key, value in item.iteritems():
            hosts = []
            assert key.startswith('on_')
            key = key[3:]
            hosts = extract_hosts(key, config)
            run_command(hosts, value, config)


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

    def upload_file(self, remote_path, local_path):
        """Copy a file to the host"""
        raise NotImplementedError()

    def retrieve_file(self, remote_path, local_path):
        """Retrieve a file from the host"""
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

    def upload_file(self, local_path, remote_path):
        """Copy a file to the host"""
        self.ftp.put(local_path, remote_path)

    def retrieve_file(self, local_path, remote_path):
        """Retrieve a file from the host"""
        self.ftp.get(remote_path, local_path)

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

    def upload_file(self, remote_path, local_path):
        """Copy a file to the host"""
        if local_path == remote_path:
            LOG.warning('Uploading file locally to same path. Skipping step')
        else:
            shutil.copyfile(local_path, remote_path)

    def retrieve_file(self, remote_path, local_path):
        """Retrieve a file from the host"""
        if local_path == remote_path:
            LOG.warning('Retrieving file locally to same path. Skipping step')
        shutil.copyfile(remote_path, local_path)
