import logging
import select
import time

import paramiko


LOG = logging.getLogger(__name__)


def log_lines(level, lines):
    """Logs a list of lines without trailing whitespace"""
    for line in lines:
        if line:
            LOG.log(level, line.rstrip())


class RemoteHost(object):
    """Represents a SSH connection to remote host."""
    def __init__(self, host, user, pem_file):
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.client.AutoAddPolicy())
        ssh.connect(host, username=user, key_filename=pem_file)
        ftp = ssh.open_sftp()
        self._ssh = ssh
        self.ftp = ftp
        self.host = host
        self.user = user

    def exec_command(self, argv):
        """Execute the command and print the output."""
        command = ' '.join(argv)
        LOG.info('[%s@%s]$ %s', self.user, self.host, command)
        stdin, stdout, stderr = self._ssh.exec_command(command)
        stdin.channel.shutdown_write()
        stdin.close()
        # Stream the output of the command to the log
        while not stdout.channel.exit_status_ready():
            read_ready, _, _ = select.select([stdout.channel], [], [])
            if read_ready:
                log_lines(logging.INFO, [stdout.readline()])
        # Log the rest of stdout and stderr
        log_lines(logging.INFO, stdout.readlines())
        exit_status = stdout.channel.recv_exit_status()
        if exit_status != 0:
            log_lines(logging.ERROR, stderr.readlines())
            LOG.error('Failed with exit status {0}'.format(exit_status))
        stdout.close()
        stderr.close()
        return exit_status

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
            self.run(['pkill', name])
            time.sleep(1)

    def kill_mongo_procs(self):
        """Kills all mongo processes on the remote host."""
        self.kill_remote_procs('mongo')

    def create_file(self, remote_path, file_contents):
        """Creates a file on the remote host"""
        with self.ftp.file(remote_path, 'w') as f:
            f.write(file_contents)
            f.flush()

    def close(self):
        """Close the ssh connection."""
        self._ssh.close()
        self.ftp.close()
