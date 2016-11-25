"""Download and install mongodb_binary_archive on all nodes."""

import logging

#pylint: disable=relative-import,too-few-public-methods
from host import RemoteHost, LocalHost

LOG = logging.getLogger(__name__)

class DownloadMongodb(object):
    """Download and install mongodb_binary_archive on all nodes."""

    def __init__(self, config, cli_mongodb_binary_archive=None, run_locally=False):

        self.run_locally = run_locally

        self.config = config

        self.mongodb_binary_archive = cli_mongodb_binary_archive
        if 'runtime' in config.keys():
            self.mongodb_binary_archive = config['runtime'].get('mongodb_binary_archive',
                                                                cli_mongodb_binary_archive)
        LOG.info("Download url is %s", self.mongodb_binary_archive)

        tfvars = config['infrastructure_provisioning']['tfvars']
        self.ssh_user = tfvars['ssh_user']
        self.ssh_key_file = tfvars['ssh_key_file']

        self.hosts = []
        self._parse_hosts()

        if self.mongodb_binary_archive:
            LOG.debug("DownloadMongodb initialized with url: %s",
                      self.mongodb_binary_archive)

    def _parse_hosts(self):
        """Parse the public_ip's out of infrastructure_provisioning.out.yml"""
        if self.run_locally:
            self.hosts = [LocalHost()]
            return
        # ["out"] contains a structure like:
        #
        # mongod:
        # - private_ip: 10.2.0.100
        #   public_ip: 54.174.16.90
        # - private_ip: 10.2.0.101
        #   public_ip: 54.173.175.242
        # - private_ip: 10.2.0.102
        #   public_ip: 52.90.69.149
        # workload_client:
        # - public_ip: 54.210.231.19
        #
        # We are flexible / future proof and accept anything that comes with a
        # public_ip.
        for val in self.config["infrastructure_provisioning"]["out"].values():
            if isinstance(val, list):
                for srv in val:
                    if 'public_ip' in srv.keys():
                        self.hosts.append(RemoteHost(srv['public_ip'],
                                                     self.ssh_user, self.ssh_key_file))

    def download_and_extract(self):
        """Download self.mongodb_binary_archive, extract it, and create some symlinks."""
        if not self.mongodb_binary_archive:
            LOG.warn("DownloadMongodb: download_and_extract() was called, "
                     + "but mongodb_binary_archive isn't defined.")
            return 1
        for host in self.hosts:
            commands = self._remote_commands(host)
            if not host.run(commands):
                return False
        return True

    def _remote_commands(self, host):
        mongo_dir = self.config["mongodb_setup"]["mongo_dir"]
        return [
            ['echo', 'Downloading {} to {}.'.format(
                self.mongodb_binary_archive, host.host)],
            ['rm', '-rf', mongo_dir],
            ['rm', '-rf', 'bin'],
            ['rm', '-rf', 'jstests'],
            ['mkdir', mongo_dir],
            ['curl', '--retry', '10', self.mongodb_binary_archive, '|',
             'tar', 'zxv', '-C', mongo_dir],
            ['cd', '..'],
            ['mv', mongo_dir + '/*/*', mongo_dir],
            ['mkdir', '-p', 'bin'],
            ['ln', '-s', '../' + mongo_dir + '/bin/mongo', 'bin/mongo'],
            ['ln', '-s', mongo_dir + '/jstests', 'jstests'],
            ['bin/mongo', '--version'],
            [mongo_dir + '/bin/mongod', '--version'],
            ['ls', '-la']
        ]
