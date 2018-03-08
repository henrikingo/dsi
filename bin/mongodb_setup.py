#!/usr/bin/env python2.7
""""
MongoDB Setup

This file takes as input a YAML configuration of the AWS instances and
MongoDB cluster topology and brings up a cluster on the remote machines.
"""
from functools import partial
import logging

import argparse
import jinja2

import common.host
from common.download_mongodb import DownloadMongodb
import common.mongodb_setup_helpers
import common.mongodb_cluster
from common.host import ONE_MINUTE_MILLIS
from common.log import setup_logging
from common.config import ConfigDict
from common.thread_runner import run_threads

LOG = logging.getLogger(__name__)


class MongodbSetup(object):
    """Parse the mongodb_setup config"""

    def __init__(self, config):
        self.config = config
        self.mongodb_setup = self.config['mongodb_setup']
        self.clusters = []
        self.parse_topologies()

        self._downloader = None

        timeouts = self.config['mongodb_setup'].get('timeouts', {})
        self.shutdown_ms = timeouts.get('shutdown_ms', 9 * ONE_MINUTE_MILLIS)
        self.sigterm_ms = timeouts.get('sigterm_ms', ONE_MINUTE_MILLIS)

    def parse_topologies(self):
        """Create cluster for each topology"""
        for topology in self.config['mongodb_setup']['topology']:
            self.clusters.append(common.mongodb_cluster.create_cluster(topology, self.config))

    def start(self):
        """Start all clusters for the first time.
           On the first start, we will just kill hard any mongod processes as quickly as
           possible. (They would most likely be left running by a previous evergreen task
           and will be wiped out anyway.)
          See :method:`restart` if this is not a clean start.
        """
        self.destroy(self.sigterm_ms)

        # The downloader will download MongoDB binaries if a URL was provided in the
        # ConfigDict.
        if not self.downloader.download_and_extract():
            LOG.error("Download and extract failed.")
            return False

        if 'pre_cluster_start' in self.config['mongodb_setup']:
            LOG.info("Mongodb_setup running pre_cluster_start commands")
            common.host.run_host_commands(self.config['mongodb_setup']['pre_cluster_start'],
                                          self.config, 'pre_cluster_start')

        return self._start()

    def add_default_user(self):
        """Add the default user.

        Required for authentication to work properly. Assumes that the cluster is already up and
        running. It must connect to the appropriate node through the local host, using the local
        host exception to add the user. Any future connections to the cluster must use the
        authentication string.

        """

        script_template = jinja2.Template('''
            db.getSiblingDB("admin").createUser(
              {
                user: {{user|tojson}},
                pwd: {{password|tojson}},
                roles: [ { role: "root", db: "admin" } ]
              });''')

        add_user_script = script_template.render(
            user=self.config['mongodb_setup']['authentication']['enabled']['username'],
            password=self.config['mongodb_setup']['authentication']['enabled']['password'])
        for cluster in self.clusters:
            cluster.run_mongo_shell(add_user_script)

    def restart(self, clean_db_dir=None, clean_logs=None):
        """
        Restart all clusters. Shutdown can fail if there was no mongod process running
        or if there is no mongo client binary (a clean host). As this is a restart these cases
        are deemed to be serious failures.

        :param clean_db_dir Should we clean db dir. If not specified, uses value from ConfigDict.
        :param clean_logs   Should we clean logs and diagnostic data. If not specified, uses value
        from ConfigDict.

          See :method:`start` if this is a clean start.
        """
        shutdown = self.shutdown(self.shutdown_ms,
                                 common.mongodb_setup_helpers.mongodb_auth_configured(self.config))
        self.destroy(self.sigterm_ms)
        if not shutdown:
            LOG.error("Shutdown failed on restart.")
            return False

        return self._start(
            is_restart=True, restart_clean_db_dir=clean_db_dir, restart_clean_logs=clean_logs)

    def _start(self, is_restart=False, restart_clean_db_dir=None, restart_clean_logs=None):

        # For a start or restart with restart_clean_db_dir True, and if Auth is configured, we need
        # to bring the cluster up twice. First without auth, then add user, then with auth
        if common.mongodb_setup_helpers.mongodb_auth_configured(
                self.config) and (not is_restart or restart_clean_db_dir):
            LOG.info("Auth configured. Starting Cluster without Auth first")
            self._start_auth_explicit(
                is_restart, restart_clean_db_dir, restart_clean_logs, enable_auth=False)
            LOG.info("Adding default user for all clusters")
            self.add_default_user()
            self.shutdown(self.shutdown_ms)
            LOG.info("Restarting MongoDB Clusters with authentication enabled")

            # After here we are doing a restart without cleaning the db_dir.
            is_restart = True
            restart_clean_db_dir = False
            restart_clean_logs = False

        return self._start_auth_explicit(
            is_restart=is_restart,
            restart_clean_db_dir=restart_clean_db_dir,
            restart_clean_logs=restart_clean_logs,
            enable_auth=common.mongodb_setup_helpers.mongodb_auth_configured(self.config))

    def _start_auth_explicit(self,
                             is_restart=False,
                             restart_clean_db_dir=None,
                             restart_clean_logs=None,
                             enable_auth=False):
        """ Complete the remaining start (either clean or restart) operations.
            Any Shutdown, destroy or downloading has been handled by the caller(
            See :method:`start` or See :method:`restart`).

        :param is_restart      This is a restart of the cluster, not the first start.
        :param restart_clean_db_dir Should we clean db dir. If not specified, uses value from
        ConfigDict.
        :param restart_clean_logs   Should we clean logs and diagnostic data. If not specified,
        uses value from ConfigDict.
        """
        if not all(
                run_threads(
                    [
                        partial(
                            self.start_cluster,
                            cluster=cluster,
                            is_restart=is_restart,
                            restart_clean_db_dir=restart_clean_db_dir,
                            restart_clean_logs=restart_clean_logs,
                            enable_auth=enable_auth) for cluster in self.clusters
                    ],
                    daemon=True)):
            LOG.error("Could not start clusters in _start. Shutting down...")
            self.shutdown(self.shutdown_ms)
            return False
        return True

    @property
    def downloader(self):
        """
        :return: DownloadMongodb instance
        """
        if self._downloader is None:
            self._downloader = DownloadMongodb(self.config)
        return self._downloader

    @downloader.setter
    def downloader(self, value):
        self._downloader = value

    @staticmethod
    def start_cluster(cluster,
                      is_restart=False,
                      restart_clean_db_dir=None,
                      restart_clean_logs=None,
                      enable_auth=False):
        """Start cluster
        :param cluster         cluster to start
        :param is_restart      This is a restart of the cluster, not the first start.
        :param restart_clean_db_dir Should we clean db dir. If not specified, uses value from
        ConfigDict.
        :param restart_clean_logs   Should we clean logs and diagnostic data. If not specified,
        uses value from ConfigDict.
        """
        LOG.info('-' * 72)
        LOG.info('starting topology: %s', cluster)
        if not cluster.setup_host(
                restart_clean_db_dir=restart_clean_db_dir, restart_clean_logs=restart_clean_logs):
            LOG.error("Could not setup host in start_cluster")
            return False
        # Don't initialize if restarting mongodb and keeping (not cleaning) the db dir
        initialize = not (is_restart and not restart_clean_db_dir)
        if not cluster.launch(initialize, enable_auth=enable_auth):
            LOG.error("Could not launch cluster in start_cluster")
            return False
        LOG.info('started topology: %s', cluster)
        return True

    def shutdown(self, max_time_ms, auth_enabled=None):
        """Shutdown all launched mongo programs
        For the max_time_ms parameter, see
            :method:`Host.exec_command`
        """
        LOG.info('Calling shutdown for %s clusters', len(self.clusters))
        result = all(
            run_threads(
                [partial(cluster.shutdown, max_time_ms, auth_enabled) for cluster in self.clusters],
                daemon=True))
        LOG.warn('shutdown: %s', 'succeeded' if result else 'failed')
        return result

    def destroy(self, max_time_ms):
        """Kill all launched mongo programs
        For the max_time_ms parameter, see
            :method:`Host.exec_command`
        """
        LOG.info('calling destroy')
        result = all(
            run_threads(
                [partial(cluster.destroy, max_time_ms) for cluster in self.clusters], daemon=True))
        LOG.warn('destroy: %s', 'succeeded' if result else 'failed')
        return result

    def close(self):
        """Close connections to all hosts."""
        run_threads([cluster.close for cluster in self.clusters], daemon=True)


def parse_command_line():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Start a MongoDB cluster in a distributed environment')
    parser.add_argument('-d', '--debug', action='store_true', help='enable debug output')
    parser.add_argument('--log-file', help='path to log file')

    return parser.parse_args()


def main():
    """Start a mongodb cluster."""
    args = parse_command_line()
    setup_logging(args.debug, args.log_file)

    config = ConfigDict('mongodb_setup')
    config.load()

    # start a mongodb configuration using config module
    mongo = MongodbSetup(config=config)
    if not mongo.start():
        LOG.error("Error setting up mongodb")
        exit(1)


if __name__ == '__main__':
    main()
