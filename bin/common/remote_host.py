"""
Provide abstraction over running commands on remote machines, extending the base class in host.py
"""

from stat import S_ISDIR
from datetime import datetime
import logging
import tempfile
import shutil
import socket
import os

import paramiko

import common.host_utils as host_utils
import common.host

from common.log import IOLogAdapter

LOG = logging.getLogger(__name__)
# This stream only log error or above messages
ERROR_ONLY = logging.getLogger('error_only')

INFO_ADAPTER = IOLogAdapter(LOG, logging.INFO)
WARN_ADAPTER = IOLogAdapter(LOG, logging.WARN)


class RemoteHost(common.host.Host):
    """
    Represents a SSH connection to a remote host
    """

    def __init__(self, host, user, pem_file, mongodb_auth_settings=None):
        """
        :param host: hostname
        :param user: username
        :param pem_file: ssh pem file
        """
        super(RemoteHost, self).__init__(host, mongodb_auth_settings)
        LOG.debug('host: %s, user: %s, pem_file: %s', host, user, pem_file)
        try:
            ssh, ftp = host_utils.connected_ssh(host, user, pem_file)
            self._ssh = ssh
            self.ftp = ftp
            self.user = user
        except (paramiko.SSHException, socket.error):
            exit(1)

    # pylint: disable=too-many-arguments
    def exec_command(self,
                     argv,
                     stdout=None,
                     stderr=None,
                     get_pty=False,
                     max_time_ms=None,
                     no_output_timeout_ms=None,
                     quiet=False):
        """
        Execute the argv command on the remote host and log the output.

        For parameters/returns, see :method: `Host.exec_command`.
        :raises: HostException for timeouts and to wrap paramiko.SSHException
        """
        if quiet:
            logger = ERROR_ONLY
        else:
            logger = LOG

        # pylint: disable=too-many-branches
        if not argv or not isinstance(argv, (list, basestring)):
            raise ValueError("Argument must be a nonempty list or string.")

        if (max_time_ms is not None and no_output_timeout_ms is not None
                and no_output_timeout_ms > max_time_ms):
            logger.warn("Can't wait %s ms for output when max time is %s ms", no_output_timeout_ms,
                        max_time_ms)

        if stdout is None:
            stdout = INFO_ADAPTER
        if stderr is None:
            stderr = WARN_ADAPTER

        if isinstance(argv, list):
            command = ' '.join(argv)
        else:
            command = argv

        logger.info('[%s@%s]$ %s', self.user, self.host, command)

        # scoping
        ssh_stdout, ssh_stderr = None, None

        try:
            ssh_stdin, ssh_stdout, ssh_stderr = self._ssh.exec_command(command, get_pty=get_pty)
            ssh_stdin.channel.shutdown_write()
            ssh_stdin.close()

            exit_status = self._perform_exec(command, stdout, stderr, ssh_stdout, ssh_stderr,
                                             max_time_ms, no_output_timeout_ms)

        except paramiko.SSHException as e:
            raise host_utils.HostException("failed to exec '{}' on {}@{}: '{}'".format(
                command, self.user, self.host, e))
        finally:
            host_utils.close_safely(ssh_stdout)
            host_utils.close_safely(ssh_stderr)

        if exit_status != 0:
            logger.warn('%s \'%s\': Failed with exit status %s', self.alias, command, exit_status)
        return exit_status

    # pylint: disable=no-self-use
    # pylint: disable=too-many-arguments
    # pylint: disable=too-many-locals
    def _perform_exec(self, command, stdout, stderr, ssh_stdout, ssh_stderr, max_time_ms,
                      no_output_timeout_ms):
        """
        For parameters/returns, see :method: `Host.exec_command`.

        :return: exit_status int 0 or None implies success
        :raises: HostException for timeouts.
        """
        total_operation_start = datetime.now()
        total_operation_is_timed_out = host_utils.create_timer(total_operation_start, max_time_ms)
        no_output_timed_out = host_utils.create_timer(datetime.now(), no_output_timeout_ms)

        # The channel settimeout causes reads to throw 'socket.timeout' if data does not arrive
        # within that time. This is not necessarily an error, it allows us to implement
        # max time ms without having to resort to threading.
        ssh_stdout.channel.settimeout(0.1)

        # Stream the output of the command to the log
        while (not total_operation_is_timed_out() and not no_output_timed_out()
               and not ssh_stdout.channel.exit_status_ready()):
            any_lines = host_utils.stream_lines(ssh_stdout, stdout)
            if any_lines:
                no_output_timed_out = host_utils.create_timer(datetime.now(), no_output_timeout_ms)

        # At this point we have either timed out or the command has finished. The code makes
        # a best effort to stream any remaining logs but the 'for line in ..' calls will
        # only block once for a max of 100 millis.
        #
        # Log the rest of stdout and stderr
        host_utils.stream_lines(ssh_stdout, stdout)
        host_utils.stream_lines(ssh_stderr, stderr)

        if ssh_stdout.channel.exit_status_ready():
            exit_status = ssh_stdout.channel.recv_exit_status()
        else:
            time_taken = (datetime.now() - total_operation_start).total_seconds()
            if no_output_timed_out():
                no_output = no_output_timeout_ms / host_utils.ONE_SECOND_MILLIS
                msg = "No Output in {} s (see test_control.timeouts.no_output_ms). {} s elapsed " \
                      "on {} for '{}'".format(no_output,
                                              time_taken,
                                              self.alias,
                                              command)
            else:
                max_time = max_time_ms / host_utils.ONE_SECOND_MILLIS
                msg = "{} exceeded {} allowable seconds on {} for '{}'".format(
                    time_taken, max_time, self.alias, command)
            raise host_utils.HostException(msg)

        return exit_status

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

        :raises: HostException on error
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
        :raises: HostException on error
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
        :raises: HostException on error
        """
        tarball_name = '{}.tar'.format(os.path.basename(remote_path))
        remote_parent_dir = os.path.dirname(remote_path)
        remote_tarball_path = os.path.join(remote_parent_dir, tarball_name)

        tarball_path = shutil.make_archive(
            os.path.join(temp_dir, tarball_name), 'tar', local_path, '.')

        # Make way and upload it
        cmd = ['mkdir', '-p', remote_path]
        exit_status = self.exec_command(cmd)
        host_utils.raise_if_not_ok(exit_status, cmd)

        try:
            # should raise an exception on error
            self._upload_single_file(tarball_path, remote_tarball_path)
        except Exception as e:  # pylint: disable=broad-except
            host_utils.reraise_as_host_exception(e)

        # Untar it. Have to rely on shell because tarfile doesn't operate remotely.
        cmd = ['tar', 'xf', remote_tarball_path, '-C', remote_path]
        exit_status = self.exec_command(cmd)
        host_utils.raise_if_not_ok(exit_status, cmd)

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
