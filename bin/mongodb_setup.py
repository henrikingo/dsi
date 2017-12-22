#!/usr/bin/env python
""""
MongoDB Setup

This file takes as input a YAML configuration of the AWS instances and
MongoDB cluster topology and brings up a cluster on the remote machines.
"""
from functools import partial
import json
import logging
import os
import time

import argparse
import yaml

# pylint does not like relative imports but "from bin.common" does not work
# pylint: disable=too-many-instance-attributes
from common.download_mongodb import DownloadMongodb
from common.host import RemoteHost, LocalHost
from common.log import setup_logging
from common.config import ConfigDict, copy_obj
from common.thread_runner import run_threads

LOG = logging.getLogger(__name__)

# Remote files that need to be created.
DEFAULT_JOURNAL_DIR = '/media/ephemeral1/journal'
DEFAULT_MONGO_DIR = 'mongodb'
DEFAULT_MEMBER_PRIORITY = 1
DEFAULT_CSRS_NAME = 'configSvrRS'


def args_list(opts):
    """Converts options dictionary by prepending '--' to the keys."""
    args = []
    for opt, val in opts.items():
        if opt == 'setParameters':
            for param, param_val in val.items():
                args.append('--setParameter={0}={1}'.format(param, param_val))
        elif val:
            args.append('--{0}={1}'.format(opt, val))
        else:
            args.append('--{0}'.format(opt))
    return args


def merge_dicts(base, override):
    """Recursively merges nested dictionaries"""
    copy = copy_obj(base)
    # update takes care of overriding non-dict values
    copy.update(override)
    for key in copy:
        if key in base and isinstance(copy[key], dict) and isinstance(base[key], dict):
            copy[key] = merge_dicts(base[key], copy[key])
    return copy


class MongoNode(object):
    """Represents a mongo[ds] program on a remote host."""

    ports_allocated = set()
    """keeps track of which ports have been locally allocated"""

    ssh_user = 'ec2-user'
    ssh_key_file = '../../keys/aws.pem'
    """ssh credentials for remote hosts, overrided by config."""

    journal_dir = DEFAULT_JOURNAL_DIR
    """Directory to symlink mongod journal"""

    clean_logs = True
    """Delete mongod.log and diagnostic.data before startup"""

    clean_db_dir = True
    """Delete data directory before startup"""

    numactl_prefix = ""
    """Set this to execute mongod via numactl"""

    shutdown_options = "{}"
    """ Set this to pass in options to shutdown"""

    def __init__(self, opts, is_mongos=False):
        """
        :param opts: Read-only options for mongo[ds], example:
        {
            'public_ip': '127.0.0.1',
            'private_ip': '127.0.0.1',
            'config_file': {},
            'mongo_dir': '/usr/bin',
            'priority': 10,
            'clean_logs': True,
            'clean_db_dir': True,
            'use_journal_mnt': True
        }
        :param is_mongos: True if this node is a mongos
        """
        self.mongo_program = 'mongos' if is_mongos else 'mongod'
        self.public_ip = opts['public_ip']
        self.private_ip = opts.get('private_ip', self.public_ip)
        self.bin_dir = os.path.join(opts.get('mongo_dir', DEFAULT_MONGO_DIR), 'bin')
        self.clean_logs = opts.get('clean_logs', MongoNode.clean_logs)
        self.clean_db_dir = opts.get('clean_db_dir', (not is_mongos) and MongoNode.clean_db_dir)
        self.use_journal_mnt = opts.get('use_journal_mnt', not is_mongos)
        self.mongo_config_file = copy_obj(opts.get('config_file', {}))
        self.logdir = os.path.dirname(self.mongo_config_file['systemLog']['path'])
        if is_mongos:
            self.dbdir = None
        else:
            self.dbdir = self.mongo_config_file['storage']['dbPath']
        self.port = self.mongo_config_file['net']['port']
        self.host = self._host()

    @staticmethod
    def get_open_port(port_hint):
        """Return an open port for the given hostname."""
        port = port_hint
        if port in MongoNode.ports_allocated:
            port = max(MongoNode.ports_allocated) + 1
        MongoNode.ports_allocated.add(port)
        return port

    def _host(self):
        """Create host wrapper to run commands."""
        # TODO: this should not use the Remote and LocalHost classes directly.
        if self.public_ip in ['localhost', '127.0.0.1', '0.0.0.0']:
            return LocalHost()
        return RemoteHost(self.public_ip, self.ssh_user, self.ssh_key_file)

    # TODO(rtimmons): refactor to MongoStatusChecker or similar to ease mocking
    def wait_until_up(self):
        """ Checks to make sure node is up and accessible"""
        js_string = '''
            i = 0
            while (db.serverStatus().ok != 1 && i < 20) {{
                print ("Waiting for node {} to come up");
                sleep(1000);
                i += 1; }}
            assert(db.serverStatus().ok == 1)'''
        i = 0
        while not self.run_mongo_shell(js_string.format(self.public_ip)) and i < 10:
            i += 1
            time.sleep(1)
        if i == 10:
            LOG.error("Node %s not up at end of wait_until_up", self.public_ip)
            return False
        return True

    def setup_host(self, restart_clean_db_dir=None, restart_clean_logs=None):
        """Ensures necessary files are setup.
        :param restart_clean_db_dir Should we clean db dir on restart. If not specified, uses value
        from ConfigDict.
        :param restart_clean_logs   Should we clean logs and diagnostic data. If not specified,
        uses value from ConfigDict.
        """
        self.host.kill_mongo_procs()

        if restart_clean_db_dir is not None:
            _clean_db_dir = restart_clean_db_dir
        else:
            _clean_db_dir = self.clean_db_dir
        _clean_logs = restart_clean_logs if restart_clean_logs is not None else self.clean_logs

        # NB: self.dbdir is None when self.is_mongos is True
        setup_cmd_args = {
            'clean_db_dir': _clean_db_dir,
            'clean_logs': _clean_logs,
            'dbdir': self.dbdir,
            'journal_dir': self.journal_dir,
            'logdir': self.logdir,
            'is_mongos': self.mongo_program == 'mongos',
            'use_journal_mnt': self.use_journal_mnt
        }
        commands = MongoNode._generate_setup_commands(setup_cmd_args)

        return self.host.run(commands)

    @staticmethod
    def _generate_setup_commands(setup_args):
        commands = []
        # Clean the logs and diagnostic data
        if setup_args['clean_logs']:
            commands.append(['rm', '-rf', os.path.join(setup_args['logdir'], '*.log')])
            commands.append(['rm', '-rf', os.path.join(setup_args['logdir'], 'core.*')])
            if not setup_args['is_mongos']:
                commands.append(
                    ['rm', '-rf',
                     os.path.join(setup_args['dbdir'], 'diagnostic.data', '*')])
        # Create the data/logs directories
        commands.append(['mkdir', '-p', setup_args['logdir']])

        if setup_args['dbdir'] and setup_args['clean_db_dir']:
            # Deleting diagnostic.data is governed by clean_logs. Don't delete it here.
            # When diagnostic.data doesn't exist, just create an empty one to avoid errors
            commands.append(['mkdir', '-p', os.path.join(setup_args['dbdir'], 'diagnostic.data')])
            commands.append(['rm', '-rf', os.path.join(setup_args['logdir'], 'diagnostic.data')])
            commands.append(
                ['mv',
                 os.path.join(setup_args['dbdir'], 'diagnostic.data'), setup_args['logdir']])

            commands.append(['rm', '-rf', setup_args['dbdir']])

            if setup_args['use_journal_mnt']:
                commands.append(['rm', '-rf', setup_args['journal_dir']])

            commands.append(['mkdir', '-p', setup_args['dbdir']])

            commands.append(
                ['mv',
                 os.path.join(setup_args['logdir'], 'diagnostic.data'), setup_args['dbdir']])

            # If not clean_db_dir assume that this has already been done.
            # Create separate journal directory and link to the database
            if setup_args['use_journal_mnt']:
                commands.append(['mkdir', '-p', setup_args['journal_dir']])
                commands.append([
                    'ln', '-s', setup_args['journal_dir'],
                    os.path.join(setup_args['dbdir'], 'journal')
                ])
            commands.append(['ls', '-la', setup_args['dbdir']])

        commands.append(['ls', '-la'])
        return commands

    def launch_cmd(self, numactl=True):
        """Returns the command to start this node."""
        remote_file_name = '/tmp/mongo_port_{0}.conf'.format(self.port)
        config_contents = yaml.dump(self.mongo_config_file, default_flow_style=False)
        self.host.create_file(remote_file_name, config_contents)
        self.host.run(['cat', remote_file_name])
        cmd = os.path.join(self.bin_dir, self.mongo_program) + " --config " + remote_file_name
        numactl_prefix = self.numactl_prefix
        if numactl and isinstance(numactl_prefix, basestring) and numactl_prefix != "":
            cmd = numactl_prefix + " " + cmd
        LOG.debug("cmd is %s", str(cmd))
        return cmd

    def launch(self, initialize=True, numactl=True):
        """Starts this node.

        :param initialize boolean: Initialize the node. This doesn't do anything for the
                                     base node"""

        # initialize is explicitly not used for now for a single node. We may want to use it in
        # the future
        _ = initialize

        if not self.host.run(self.launch_cmd(numactl)):
            self.dump_mongo_log()
            return False
        return self.wait_until_up()

    def run_mongo_shell(self, js_string):
        """
        Run JavaScript code in a mongo shell on the underlying host
        :param js_string: String of JavaScript code.
        :return: True if the mongo shell exits successfully
        """
        remote_file_name = '/tmp/mongo_port_{0}.js'.format(self.port)
        if self.host.exec_mongo_command(js_string, remote_file_name,
                                        "localhost:" + str(self.port)) != 0:
            self.dump_mongo_log()
            return False
        return True

    def dump_mongo_log(self):
        """Dump the mongo[ds] log file to the process log"""
        LOG.info('Dumping log for node %s', self.hostport_public())
        self.host.run(['cat', self.mongo_config_file['systemLog']['path']])

    def hostport_private(self):
        """Returns the string representation this host/port."""
        return '{0}:{1}'.format(self.private_ip, self.port)

    connection_string_private = hostport_private

    def hostport_public(self):
        """Returns the string representation this host/port."""
        return '{0}:{1}'.format(self.public_ip, self.port)

    connection_string_public = hostport_public

    def shutdown(self):
        """Shutdown the replset members gracefully"""
        try:
            return self.run_mongo_shell('db.getSiblingDB("admin").shutdownServer({})'.format(
                self.shutdown_options))
        except Exception:  # pylint: disable=broad-except
            LOG.error("Error shutting down MongoNode at %s:%s", self.public_ip, self.port)

    def destroy(self):
        """Kills the remote mongo program."""
        self.host.kill_mongo_procs()
        # Clean up any old lock files. Server shouldn't be running at this point.
        if self.dbdir:
            self.host.run(['rm', '-rf', os.path.join(self.dbdir, 'mongod.lock')])

    def close(self):
        """Closes SSH connections to remote hosts."""
        self.host.close()

    def __str__(self):
        """String describing this node"""
        return '{}: {}'.format(self.mongo_program, self.hostport_public())


class ReplSet(object):
    """Represents a replica set on remote hosts."""

    replsets = 0
    """Counts the number of ReplSets created."""

    def __init__(self, opts):
        """

        :param opts: Read-only options for  replSet, example:
        {
            'id': 'replSetName',
            'configsvr': False,
            'mongod': [MongoNode opts, ...],
        }
        """
        self.name = opts.get('id')
        if not self.name:
            self.name = 'rs{}'.format(ReplSet.replsets)
            ReplSet.replsets += 1
        self.configsvr = opts.get('configsvr', False)
        self.mongod_opts = opts['mongod']
        self.rs_conf = opts.get('rs_conf', {})
        self.rs_conf_members = []
        self.nodes = []
        for opt in self.mongod_opts:
            # save replica set member configs
            self.rs_conf_members.append(copy_obj(opt.get('rs_conf_member', {})))
            # Must add replSetName and clusterRole
            config_file = copy_obj(opt.get('config_file', {}))
            config_file = merge_dicts(config_file, {'replication': {'replSetName': self.name}})

            mongod_opt = copy_obj(opt)
            if self.configsvr:
                config_file = merge_dicts(config_file, {'sharding': {'clusterRole': 'configsvr'}})
                # The test infrastructure does not set up a separate journal dir for
                # the config server machines.
                mongod_opt['use_journal_mnt'] = False
            mongod_opt['config_file'] = config_file
            self.nodes.append(MongoNode(mongod_opt))

    def is_any_priority_set(self):
        """Returns true if a priority is set for any node."""
        for member in self.rs_conf_members:
            if 'priority' in member:
                return True
        return False

    def highest_priority_node(self):
        """Returns the highest priority node."""
        max_node = self.nodes[0]
        max_priority = -1
        for node, member in zip(self.nodes, self.rs_conf_members):
            if 'priority' in member and member['priority'] > max_priority:
                max_node = node
                max_priority = member['priority']
        return max_node

    def wait_until_up(self):
        """ Checks and waits for all nodes in replica set to be either PRIMARY or SECONDARY"""
        primary_js_string = '''
            i = 0;
            while (!rs.isMaster().ismaster && i < 20) {{
                print("Waiting for expected primary to become master...");
                sleep(1000);
            }}
            assert(rs.isMaster().ismaster);
            rs.slaveOk();
            print("rs.status(): " + tojson(rs.status()));
            print("rs.config(): " + tojson(rs.config()));'''
        # Wait for Primary to be up
        primary = self.highest_priority_node()
        if not primary.run_mongo_shell(primary_js_string):
            LOG.error("RS Node %s not up as primary", primary.public_ip)
            return False

        js_string = '''
            i = 0
            while(!rs.isMaster().ismaster && !rs.isMaster().secondary && i < 20) {{
                print ("Waiting for node {} to come up");
                sleep(1000);
                i += 1; }}'''
        # Make sure all nodes are primary or secondary
        for node in self.nodes:
            if not node.run_mongo_shell(js_string.format(node.public_ip)):
                LOG.error("RS Node %s not up at end of wait_until_up", node.public_ip)
                return False
        return True

    def setup_host(self, restart_clean_db_dir=None, restart_clean_logs=None):
        """Ensures necessary files are setup.
        :param restart_clean_db_dir Should we clean db dir. If not specified, uses value from
        ConfigDict.
        :param restart_clean_logs   Should we clean logs and diagnostic data. If not specified,
        uses value from ConfigDict.
        """
        return all(
            run_threads(
                [
                    partial(
                        node.setup_host,
                        restart_clean_db_dir=restart_clean_db_dir,
                        restart_clean_logs=restart_clean_logs) for node in self.nodes
                ],
                daemon=True))

    def launch(self, initialize=True, numactl=True):
        """Starts the replica set.
        :param initialize boolean: Initialize the replica set"""
        if not all(
                run_threads(
                    [partial(node.launch, initialize, numactl)
                     for node in self.nodes], daemon=True)):
            return False
        if initialize:
            # Give the first host the highest priority so it will become
            # primary. This is the default behavior.
            if not self.is_any_priority_set():
                for member in self.rs_conf_members:
                    member['priority'] = DEFAULT_MEMBER_PRIORITY
                self.rs_conf_members[0]['priority'] = DEFAULT_MEMBER_PRIORITY + 1
            primary = self.highest_priority_node()
            if not primary.run_mongo_shell(self._init_replica_set()):
                return False
        # Wait for all nodes to be up
        return self.wait_until_up()

    def _init_replica_set(self):
        """Return the JavaScript code to configure the replica set."""
        LOG.info('Configuring replica set: %s', self.name)
        config = merge_dicts(self.rs_conf, {'_id': self.name, 'members': []})
        if self.configsvr:
            config['configsvr'] = True
        for i, node in enumerate(self.nodes):
            member_conf = merge_dicts(self.rs_conf_members[i], {
                '_id': i,
                'host': node.hostport_private()
            })
            config['members'].append(member_conf)
        json_config = json.dumps(config)
        js_string = '''
            config = {0};
            assert.commandWorked(rs.initiate(config),
                                 "Failed to initiate replica set!");
            '''.format(json_config)
        return js_string

    def shutdown(self):
        """Shutdown the replset members gracefully"""
        return all(run_threads([node.shutdown for node in self.nodes], daemon=True))

    def destroy(self):
        """Kills the remote replica members."""
        run_threads([node.destroy for node in self.nodes], daemon=True)

    def close(self):
        """Closes SSH connections to remote hosts."""
        run_threads([node.close for node in self.nodes], daemon=True)

    def connection_string(self, hostport_fn):
        """Returns the connection string using the hostport_fn function"""
        rs_str = ['{0}/{1}'.format(self.name, hostport_fn(self.nodes[0]))]
        for node in self.nodes[1:]:
            rs_str.append(hostport_fn(node))
        return ','.join(rs_str)

    def connection_string_private(self):
        """Returns the string representation this replica set."""
        return self.connection_string(lambda node: node.hostport_private())

    def connection_string_public(self):
        """Returns the public string representation this replica set."""
        return self.connection_string(lambda node: node.hostport_public())

    def __str__(self):
        """String describing this ReplSet"""
        return 'ReplSet: {}'.format(self.connection_string_public())


class ShardedCluster(object):
    """Represents a sharded cluster on remote hosts."""

    def __init__(self, opts):
        """

        :param opts: Read-only options for a sharded cluster:
        {
            'disable_balancer': False,
            'configsvr_type': 'csrs',
            'mongos': [MongoNodeConfig, ...],
            'configsvr': [MongoNodeConfig, ...],
            'shard': [ReplSetConfig, ...]
        }
        """
        self.disable_balancer = opts.get('disable_balancer', True)
        self.mongos_opts = opts['mongos']
        config_type = opts.get('configsvr_type', 'csrs')
        if config_type != 'csrs':
            raise NotImplementedError('configsvr_type: {}'.format(config_type))
        config_opt = {'id': DEFAULT_CSRS_NAME, 'configsvr': True, 'mongod': opts['configsvr']}
        self.config = ReplSet(config_opt)
        self.shards = []
        self.mongoses = []
        for opt in opts['shard']:
            self.shards.append(create_cluster(opt))
        for opt in opts['mongos']:
            # add the connection string for the configdb
            config_file = copy_obj(opt.get('config_file', {}))
            configdb_yaml = {'sharding': {'configDB': self.config.connection_string_private()}}
            config_file = merge_dicts(config_file, configdb_yaml)
            mongos_opt = copy_obj(opt)
            mongos_opt['config_file'] = config_file
            self.mongoses.append(MongoNode(mongos_opt, is_mongos=True))

    def wait_until_up(self):
        """Checks to make sure sharded cluster is up and
        accessible. Specifically checking that the mognos's are up"""
        num_shards = len(self.shards)
        js_string = '''
            db = db.getSiblingDB("config");
            i = 0;
            while (db.shards.count() < {0} && i < 10) {{
                print ("Waiting for mongos {1} to see {0} shards");
                sleep(1000);
                i += 1; }}
            assert (db.shards.count() == {0}) '''
        for mongos in self.mongoses:
            if not mongos.run_mongo_shell(js_string.format(num_shards, mongos.public_ip)):
                LOG.error("Mongos %s does not see right number of shards at end of wait_until_up",
                          mongos.public_ip)
                return False
        return True

    def setup_host(self, restart_clean_db_dir=None, restart_clean_logs=None):
        """Ensures necessary files are setup.
        :param restart_clean_db_dir Should we clean db dir. If not specified, uses value from
        ConfigDict.
        :param restart_clean_logs   Should we clean logs and diagnostic data. If not specified,
        uses value from ConfigDict.
        """
        commands = []
        commands.append(
            partial(
                self.config.setup_host,
                restart_clean_db_dir=restart_clean_db_dir,
                restart_clean_logs=restart_clean_logs))
        commands.extend(
            partial(
                shard.setup_host,
                restart_clean_db_dir=restart_clean_db_dir,
                restart_clean_logs=restart_clean_logs) for shard in self.shards)
        commands.extend(
            partial(
                mongos.setup_host,
                restart_clean_db_dir=restart_clean_db_dir,
                restart_clean_logs=restart_clean_logs) for mongos in self.mongoses)
        return all(run_threads(commands, daemon=True))

    def launch(self, initialize=True):
        """Starts the sharded cluster.

        :param initialize boolean: Initialize the cluster
        """
        LOG.info('Launching sharded cluster...')
        commands = []
        commands.append(partial(self.config.launch, initialize=initialize, numactl=False))
        commands.extend(partial(shard.launch, initialize=initialize) for shard in self.shards)
        commands.extend(partial(mongos.launch, initialize=initialize) for mongos in self.mongoses)
        if not all(run_threads(commands, daemon=True)):
            return False
        if initialize:
            if not self._add_shards():
                return False
        if self.disable_balancer and not self.mongoses[0].run_mongo_shell('sh.stopBalancer();'):
            return False
        return self.wait_until_up()

    def _add_shards(self):
        """Adds each shard to the cluster."""
        LOG.info('Configuring sharded cluster...')
        # Add shard to mongos
        js_add_shards = []
        for shard in self.shards:
            js_add_shards.append('assert.commandWorked(sh.addShard("{0}"));'.format(
                shard.connection_string_private()))
        if not self.mongoses[0].run_mongo_shell('\n'.join(js_add_shards)):
            LOG.error('Failed to add shards!')
            return False
        return True

    def shutdown(self):
        """Shutdown the mongodb cluster gracefully."""
        commands = []
        commands.extend(shard.shutdown for shard in self.shards)
        commands.append(self.config.shutdown)
        commands.extend(mongos.shutdown for mongos in self.mongoses)
        return all(run_threads(commands, daemon=True))

    def destroy(self):
        """Kills the remote cluster members."""
        run_threads([shard.destroy for shard in self.shards], daemon=True)
        self.config.destroy()
        run_threads([mongos.destroy for mongos in self.mongoses], daemon=True)

    def close(self):
        """Closes SSH connections to remote hosts."""
        run_threads([shard.close for shard in self.shards], daemon=True)
        self.config.close()
        run_threads([mongos.close for mongos in self.mongoses], daemon=True)

    def __str__(self):
        """String describing the sharded cluster"""
        description = ['ShardedCluster:', 'configsvr: {}'.format(self.config)]
        for shard in self.shards:
            description.append('shard: {}'.format(shard))
        for mongos in self.mongoses:
            description.append(str(mongos))
        return '\n'.join(description)


def create_cluster(topology):
    """Create MongoNode, ReplSet, or ShardCluster from topology config"""
    cluster_type = topology['cluster_type']
    LOG.info('creating topology: %s', cluster_type)
    if cluster_type == 'standalone':
        return MongoNode(topology)
    elif cluster_type == 'replset':
        return ReplSet(topology)
    elif cluster_type == 'sharded_cluster':
        return ShardedCluster(topology)
    else:
        LOG.fatal('unknown cluster_type: %s', cluster_type)
        exit(1)


class MongodbSetup(object):
    """Parse the mongodb_setup config"""

    def __init__(self, config):
        self.config = config
        self.mongodb_setup = config['mongodb_setup']
        journal_dir = self.mongodb_setup.get('journal_dir')
        if journal_dir:
            MongoNode.journal_dir = journal_dir
        MongoNode.ssh_user = config['infrastructure_provisioning']['tfvars']['ssh_user']
        ssh_key_file = config['infrastructure_provisioning']['tfvars']['ssh_key_file']
        ssh_key_file = os.path.expanduser(ssh_key_file)
        MongoNode.ssh_key_file = ssh_key_file
        MongoNode.numactl_prefix = config['infrastructure_provisioning']['numactl_prefix']
        if MongoNode.numactl_prefix is None:
            MongoNode.numactl_prefix = ""
        MongoNode.clean_logs = config['mongodb_setup'].get('clean_logs', True)
        MongoNode.clean_db_dir = config['mongodb_setup'].get('clean_db_dir', True)
        MongoNode.shutdown_options = json.dumps(
            copy_obj(config['mongodb_setup']['shutdown_options']))
        self.clusters = []
        self.downloader = DownloadMongodb(config)
        self.parse_topologies()

    def parse_topologies(self):
        """Create cluster for each topology"""
        for topology in self.mongodb_setup['topology']:
            self.clusters.append(create_cluster(topology))

    def start(self):
        """Start all clusters
        """
        return self._start()

    def restart(self, clean_db_dir=None, clean_logs=None):
        """Restart all clusters
        :param clean_db_dir Should we clean db dir. If not specified, uses value from ConfigDict.
        :param clean_logs   Should we clean logs and diagnostic data. If not specified, uses value
        from ConfigDict.
        """
        # _start() always calls shutdown() and destroy()
        return self._start(
            is_restart=True, restart_clean_db_dir=clean_db_dir, restart_clean_logs=clean_logs)

    def _start(self, is_restart=False, restart_clean_db_dir=None, restart_clean_logs=None):
        """Shutdown and destroy. Then start all clusters.
        :param is_restart      This is a restart of the cluster, not the first start.
        :param restart_clean_db_dir Should we clean db dir. If not specified, uses value from
        ConfigDict.
        :param restart_clean_logs   Should we clean logs and diagnostic data. If not specified,
        uses value from ConfigDict.
        """
        self.shutdown()
        self.destroy()
        if not is_restart:
            # The downloader will download MongoDB binaries if a URL was provided in the
            # ConfigDict.
            if not self.downloader.download_and_extract():
                LOG.error("Download URL was not provided in the ConfigDict.")
                return False
        if not all(
                run_threads(
                    [
                        partial(
                            self.start_cluster,
                            cluster=cluster,
                            is_restart=is_restart,
                            restart_clean_db_dir=restart_clean_db_dir,
                            restart_clean_logs=restart_clean_logs) for cluster in self.clusters
                    ],
                    daemon=True)):
            LOG.error("Could not start clusters in _start. Shutting down...")
            self.shutdown()
            return False
        return True

    @staticmethod
    def start_cluster(cluster, is_restart=False, restart_clean_db_dir=None,
                      restart_clean_logs=None):
        """Start cluster
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
        if not cluster.launch(initialize):
            LOG.error("Could not launch cluster in start_cluster")
            return False
        LOG.info('started topology: %s', cluster)
        return True

    def shutdown(self):
        """Shutdown all launched mongo programs"""
        run_threads([cluster.shutdown for cluster in self.clusters], daemon=True)

    def destroy(self):
        """Kill all launched mongo programs"""
        run_threads([cluster.destroy for cluster in self.clusters], daemon=True)

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

    # start a mongodb configuration using config module
    config = ConfigDict('mongodb_setup')
    config.load()
    mongo = MongodbSetup(config)
    if not mongo.start():
        LOG.error("Error setting up mongodb")
        exit(1)


if __name__ == '__main__':
    main()
