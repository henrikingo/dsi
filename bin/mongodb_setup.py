#!/usr/bin/env python3
"""
MongoDB Setup

This file takes as input a YAML configuration of the AWS instances and
MongoDB cluster topology and brings up a cluster on the remote machines.
"""
import sys
from functools import partial
import logging

import argparse

import common.atlas_setup as atlas_setup
from common.delays import safe_reset_all_delays
import common.host_utils
from common.command_runner import run_pre_post_commands, EXCEPTION_BEHAVIOR, run_upon_error
from common.download_mongodb import DownloadMongodb
import common.mongodb_setup_helpers
import common.mongodb_cluster
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

        self._downloader = None

        timeouts = self.config['mongodb_setup'].get('timeouts', {})
        self.shutdown_ms = timeouts.get('shutdown_ms', 9 * common.host_utils.ONE_MINUTE_MILLIS)
        self.sigterm_ms = timeouts.get('sigterm_ms', common.host_utils.ONE_MINUTE_MILLIS)

        self.parse_topologies()
        self.atlas = atlas_setup.AtlasSetup(config)

    def parse_topologies(self):
        """Create cluster for each topology"""
        for topology in self.mongodb_setup.get('topology', []):
            self.clusters.append(common.mongodb_cluster.create_cluster(topology, self.config))

    def add_default_users(self):
        """
        Call MongoCluster.add_default_users() on each cluster.
        """
        for cluster in self.clusters:
            cluster.add_default_users()

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

        LOG.info("Mongodb_setup running pre_cluster_start commands")
        run_pre_post_commands('pre_cluster_start', [self.config['mongodb_setup']], self.config,
                              EXCEPTION_BEHAVIOR.EXIT)

        status = self._start()
        # Start Atlas clusters using config given in mongodb_setup.atlas (if any).
        status = status and self.atlas.start()

        LOG.info("Mongodb_setup running post_cluster_start commands")
        # Exit also here. Among other things it causes setup failure in Evergreen.
        run_pre_post_commands('post_cluster_start', [self.config['mongodb_setup']], self.config,
                              EXCEPTION_BEHAVIOR.EXIT)

        return status

    def restart(self, clean_db_dir=None, clean_logs=None, nodes=None):
        """
        Restart all clusters.

        :param bool clean_db_dir: Should we clean db dir. If not specified, uses ConfigDict.
        :param bool clean_logs:   Should we clean logs and diagnostic data. If not specified, uses
                                  value from ConfigDict.
        :param list(str) nodes:   List of id's that match 'id:' keys in mongodb_setup.topology.
                                  If specified, only restart matching nodes, replica sets or
                                  clusters. If not specified (default), restart everything.

          See :method:`start` if this is a clean start.
        """
        LOG.debug("MongodbSetup.restart(%s, %s, %s)", clean_db_dir, clean_logs, nodes)
        assert not (clean_db_dir and nodes), "nodes is not supported when clean_db_dir=True"

        shutdown = self.shutdown(self.shutdown_ms,
                                 common.mongodb_setup_helpers.mongodb_auth_configured(self.config),
                                 nodes=nodes)
        destroy = self.destroy(self.sigterm_ms, nodes=nodes)
        if not (shutdown or destroy):
            LOG.error("Shutdown failed on restart.")
            return False

        return self._start(is_restart=True,
                           restart_clean_db_dir=clean_db_dir,
                           restart_clean_logs=clean_logs,
                           nodes=nodes)

    def _start(self,
               is_restart=False,
               restart_clean_db_dir=None,
               restart_clean_logs=None,
               nodes=None):

        # For a start or restart with restart_clean_db_dir True, and if Auth is configured, we need
        # to bring the cluster up twice. First without auth, then add user, then with auth
        if common.mongodb_setup_helpers.mongodb_auth_configured(
                self.config) and (not is_restart or restart_clean_db_dir):
            LOG.info("Auth configured. Starting Cluster without Auth first")
            self._start_auth_explicit(is_restart,
                                      restart_clean_db_dir,
                                      restart_clean_logs,
                                      enable_auth=False)
            LOG.info("Adding default users for all clusters")
            self.add_default_users()
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
            nodes=nodes,
            enable_auth=common.mongodb_setup_helpers.mongodb_auth_configured(self.config))

    # pylint: disable=too-many-arguments
    def _start_auth_explicit(self,
                             is_restart=False,
                             restart_clean_db_dir=None,
                             restart_clean_logs=None,
                             nodes=None,
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
                run_threads([
                    partial(self.start_cluster,
                            cluster=cluster,
                            is_restart=is_restart,
                            restart_clean_db_dir=restart_clean_db_dir,
                            restart_clean_logs=restart_clean_logs,
                            nodes=nodes,
                            enable_auth=enable_auth) for cluster in self.clusters
                ],
                            daemon=True)):
            LOG.error("Could not start clusters in _start. Shutting down...")
            self.shutdown(self.shutdown_ms, nodes=nodes)
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
                      nodes=None,
                      enable_auth=False):
        """Start cluster
        :param cluster         cluster to start
        :param is_restart      This is a restart of the cluster, not the first start.
        :param restart_clean_db_dir Should we clean db dir. If not specified, uses value from
        ConfigDict.
        :param restart_clean_logs   Should we clean logs and diagnostic data. If not specified,
        uses value from ConfigDict.
        For the nodes parameter, see :method:`MongodbSetup.restart`
        """
        LOG.info('-' * 72)
        LOG.info('starting topology: %s', cluster)
        if not cluster.setup_host(restart_clean_db_dir=restart_clean_db_dir,
                                  restart_clean_logs=restart_clean_logs,
                                  nodes=nodes):
            LOG.error("Could not set up host in start_cluster")
            return False
        # Don't initialize if restarting mongodb and keeping (not cleaning) the db dir
        initialize = not (is_restart and not restart_clean_db_dir)
        if not cluster.launch(initialize, enable_auth=enable_auth, nodes=nodes):
            LOG.error("Could not launch cluster in start_cluster")
            return False
        LOG.info('started topology: %s', cluster)
        return True

    def shutdown(self, max_time_ms, auth_enabled=None, nodes=None):
        """Shutdown all launched mongo programs
        For the max_time_ms parameter, see
            :method:`Host.exec_command`
        For the nodes parameter, see
            :method:`MongodbSetup.restart`
        """
        LOG.info('Calling shutdown for %s clusters', len(self.clusters))
        if nodes:
            LOG.info('...on a subset of nodes only: %s', str(nodes))
        result = all(
            run_threads([
                partial(cluster.shutdown, max_time_ms, auth_enabled, nodes=nodes)
                for cluster in self.clusters
            ],
                        daemon=True))
        LOG.warning('shutdown: %s', 'succeeded' if result else 'failed')
        return result

    def destroy(self, max_time_ms, nodes=None):
        """Kill all launched mongo programs
        For the max_time_ms parameter, see
            :method:`Host.exec_command`
        For the nodes parameter, see
            :method:`MongodbSetup.restart`
        """
        LOG.info('calling destroy')
        result = all(
            run_threads([partial(cluster.destroy, max_time_ms, nodes) for cluster in self.clusters],
                        daemon=True))
        if not result:
            LOG.warning('destroy: failed')
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


def start_cluster(mongo, config):
    """Start the mongodb cluster and handle any errors. This function calls sys.exit on error.
    :param MongodbSetup mongo: the mongodb setup instance.
    :param ConfigDict config: the config dict containing the task configuration.
    """
    if not mongo.start():
        LOG.error("Error in mongodb_setup.")
        LOG.warning("Attempting to execute error handling tasks.")
        run_upon_error('mongodb_setup', [config['mongodb_setup']], config)
        sys.exit(1)


def main():
    """ Handle the main functionality (parse args /setup logging ) and then start the mongodb
    cluster."""
    args = parse_command_line()
    setup_logging(args.debug, args.log_file)

    config = ConfigDict('mongodb_setup')
    config.load()

    # Delays should be unset at the end of each test_control.py run, but if it didn't complete...
    safe_reset_all_delays(config)

    # Start MongoDB cluster(s) using config given in mongodb_setup.topology (if any).
    # Note: This also installs mongo client binary onto workload client.
    mongo = MongodbSetup(config=config)

    start_cluster(mongo, config)


if __name__ == '__main__':
    main()
