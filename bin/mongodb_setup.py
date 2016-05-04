#!/usr/bin/env python
""""
MongoDB Setup

This file takes as input a YAML configuration of the AWS instances and
MongoDB cluster topology and brings up a cluster on the remote machines.
"""
import json
import logging
import os
import sys

import argparse

from common.host import RemoteHost
from common.log import setup_logging
from common.settings import source


LOG = logging.getLogger(__name__)
# This is the state the other scripts set up before cluster configure.
DSI_DIR = os.path.dirname(sys.path[0])

# Remote files that need to be created.
DEFAULT_LOG_DIR = 'data/logs'
MONGOS_LOG = os.path.join(DEFAULT_LOG_DIR, 'mongos.log')
MONGOD_LOG = os.path.join(DEFAULT_LOG_DIR, 'mongod.log')
DB_DIR = 'data/dbs'
JOURNAL_DIR = '/media/ephemeral1/journal'
DEFAULT_BIN_DIR = 'mongodb'
DEFAULT_MEMBER_PRIORITY = 1
DEFAULT_CSRS_NAME = 'configSvrRS'
DEFAULT_MONGOD_OPTS = {
    'storageEngine': 'wiredTiger',
    'dbpath': DB_DIR,
    'logpath': MONGOD_LOG,
    'port': 27017,
    'fork': '',
    'setParameters': {
        'enableTestCommands': 1
    }
}
DEFAULT_MONGOS_OPTS = {
    'logpath': MONGOS_LOG,
    'port': 27017,
    'fork': '',
    'setParameters': {
        'enableTestCommands': 1
    }
}
DEFAULT_MONGO_OPTS = {
    'verbose': ''
}


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
    """Merges base dictionary with override dictionary"""
    copy = base.copy()
    copy.update(override)
    return copy


def merge_options(base, override):
    """Merges mongo options dict."""
    copy = merge_dicts(base, override)
    # Also merge in setParameter options
    if 'setParameters' in base and 'setParameters' in override:
        copy['setParameters'] = merge_dicts(base['setParameters'],
                                            override['setParameters'])
    return copy


class MongoNode(object):
    """Represents a mongo[ds] program on a remote host."""
    def __init__(self, opts, is_mongos=False):
        self.mongo_program = 'mongos' if is_mongos else 'mongod'
        self.host = opts['host']
        self.host_private = opts.get('host_private', self.host)
        self.bin_dir = opts.get('bin_dir', DEFAULT_BIN_DIR)
        self.priority = opts.get('priority', DEFAULT_MEMBER_PRIORITY)
        self.add_to_replica = opts.get('add_to_replica', True)
        self.clean_logs = opts.get('clean_logs', True)
        self.clean_data = opts.get('clean_data', not is_mongos)
        self.use_journal_mnt = opts.get('use_journal_mnt', not is_mongos)
        self.program_args = opts.get('program_args', {})
        default = DEFAULT_MONGOS_OPTS if is_mongos else DEFAULT_MONGOD_OPTS
        self.program_args = merge_dicts(default, self.program_args)
        self.logdir = os.path.dirname(self.program_args['logpath'])
        self.dbdir = self.program_args.get('dbpath')
        self.port = self.program_args['port']
        self.remote_host = RemoteHost(
            self.host, os.environ['SSHUSER'], os.environ['PEMFILE'])

    def setup_host(self):
        """Ensures necessary files are setup."""
        self.remote_host.kill_mongo_procs()
        # limit max processes and enable core files
        commands = []
        # Clean the data/logs directories
        if self.clean_logs:
            commands.append(['rm', '-rf', os.path.join(self.logdir, '*.log')])
        # Create the data/logs directories
        commands.append(['mkdir', '-p', self.logdir])
        if self.dbdir:
            if self.clean_data:
                commands.append(['rm', '-rf', self.dbdir])
                if self.use_journal_mnt:
                    commands.append(['rm', '-rf', JOURNAL_DIR])
            commands.append(['mkdir', '-p', self.dbdir])
            # Create separate journal directory and link to the database
            if self.use_journal_mnt:
                commands.append(['mkdir', '-p', JOURNAL_DIR])
                commands.append(['ln', '-s', JOURNAL_DIR,
                                 os.path.join(self.dbdir, 'journal')])
            commands.append(['ls', '-la', self.dbdir])
        commands.append(['ls', '-la'])
        return self.remote_host.run(commands)

    def launch_cmd(self):
        """Returns the command to start this node."""
        argv = [os.path.join(self.bin_dir, 'bin', self.mongo_program)]
        argv.extend(args_list(self.program_args))
        return argv

    def launch(self):
        """Starts this node."""
        # Adjust ulimit so that mongod/s does not run out of files.
        argv = ['ulimit', '-n', '3000', '-c', 'unlimited', '&&']
        argv.extend(self.launch_cmd())
        return self.remote_host.run(argv)

    def destroy(self):
        """Kills the remote mongo program."""
        self.remote_host.kill_mongo_procs()

    def mongo_shell_cmd(self, js_file_path):
        """
        Returns the command to run js_file_path in a mongo shell on the
        underlying host.
        :param js_file_path: Path to JavaScript file.
        """
        opts = {
            'verbose': '',
            'port': self.port
        }
        argv = [os.path.join(self.bin_dir, 'bin', 'mongo')]
        argv.extend(args_list(opts))
        argv.append(js_file_path)
        return argv

    def run_mongo_shell(self, js_string):
        """
        Run JavaScript code in a mongo shell on the underlying host
        :param js_string: String of JavaScript code.
        :return: True if the mongo shell exits successfully
        """
        remote_file_name = '/tmp/mongo_port_{0}.js'.format(self.port)
        self.remote_host.create_file(remote_file_name, js_string)
        self.remote_host.run(['cat', remote_file_name])
        return self.remote_host.run(self.mongo_shell_cmd(remote_file_name))

    def close(self):
        """Closes SSH connections to remote hosts."""
        self.remote_host.close()

    def hostport(self):
        """Returns the string representation this host/port."""
        return '{0}:{1}'.format(self.host_private, self.port)


class ReplSet(object):
    """Represents a replica set on remote hosts."""
    def __init__(self, opts):
        self.name = opts['name']
        self.configsvr = opts.get('configsvr', False)
        self.node_opts = opts['node_opts']
        self.nodes = []
        for opt in self.node_opts:
            opt['program_args'] = opt.get('program_args', {})
            opt['program_args']['replSet'] = self.name
            if self.configsvr:
                opt['program_args']['configsvr'] = ''
            self.nodes.append(MongoNode(opt))

    def is_any_priority_set(self):
        """Returns true if a priority is set for any node."""
        for node_opt in self.node_opts:
            if 'priority' in node_opt:
                return True
        return False

    def highest_priority_node(self):
        """Returns the highest priority node."""
        max_node = self.nodes[0]
        for node in self.nodes[1:]:
            if node.priority > max_node.priority:
                max_node = node
        return max_node

    def setup_host(self):
        """Ensures necessary files are setup."""
        return all(node.setup_host() for node in self.nodes)

    def launch(self):
        """Starts the replica set."""
        if not all(node.launch() for node in self.nodes):
            return False
        primary = self.highest_priority_node()
        return primary.run_mongo_shell(self._init_replica_set())

    def _init_replica_set(self):
        """Return the JavaScript code to configure the replica set."""
        LOG.info('Configuring replica set: %s', self.name)
        config = {
            '_id': self.name,
            'members': []
        }
        if self.configsvr:
            config['configsvr'] = True
        for i, node in enumerate(self.nodes):
            if node.add_to_replica:
                config['members'].append({
                    '_id': i,
                    'host': node.hostport(),
                    'priority': node.priority
                })
        if not self.is_any_priority_set():
            # Give the first host the highest priority so it will become
            # primary. This is the default behavior.
            config['members'][0]['priority'] = DEFAULT_MEMBER_PRIORITY + 1
        json_config = json.dumps(config)
        js_string = '''
            config = {0};
            assert.commandWorked(rs.initiate(config),
                                 "Failed to initiate replica set!");
            while (!rs.isMaster().ismaster) {{
                sleep(1000);
                jsTestLog("Waiting for expected primary to become master...");
            }}
            rs.slaveOk();
            jsTestLog("rs.status(): " + tojson(rs.status()));
            jsTestLog("rs.config(): " + tojson(rs.config()));
            '''.format(json_config)
        return js_string

    def destroy(self):
        """Kills the remote replica members."""
        for node in self.nodes:
            node.destroy()

    def close(self):
        """Closes SSH connections to remote hosts."""
        for node in self.nodes:
            node.close()

    def connection_string(self):
        """Returns the string representation this replica set."""
        rs_str = ['{0}/{1}'.format(self.name, self.nodes[0].hostport())]
        for node in self.nodes[1:]:
            rs_str.append(node.hostport())
        return ','.join(rs_str)


class ShardedCluster(object):
    """Represents a sharded cluster on remote hosts.
    {
        'disable_balancer': False,
        'mongos_opts': [{
            'host': '1.2.3.4',
            'bin_dir': 'mongodb',
            'program_args': {
                'port': 27017,
                'storageEngine': 'wiredTiger'
            }
        }],
        config_opt: ReplSetConfig,
        shard_opts: [ReplSetConfig, ...]
    }"""
    def __init__(self, opts):
        self.disable_balancer = opts.get('disable_balancer', True)
        self.config_opt = opts['config_opt']
        self.shard_opts = opts['shard_opts']
        self.mongos_opts = opts['mongos_opts']
        self.config_opt['configsvr'] = True
        self.config_opt['name'] = self.config_opt.get('name',
                                                      DEFAULT_CSRS_NAME)
        # The test infrastructure does not set up a separate journal dir for
        # the config server machines.
        for opt in self.config_opt['node_opts']:
            opt['use_journal_mnt'] = False
        self.config = ReplSet(self.config_opt)
        self.shards = []
        self.mongoses = []
        for i, opt in enumerate(opts['shard_opts']):
            # The replica set name defaults to 'rs0', 'rs1', ...
            opt['name'] = opt.get('name', 'rs{0}'.format(i))
            self.shards.append(ReplSet(opt))
        for opt in opts['mongos_opts']:
            args = opt.get('program_args', {})
            args['configdb'] = args.get('configdb',
                                        self.config.connection_string())
            opt['program_args'] = args
            self.mongoses.append(MongoNode(opt, is_mongos=True))

    def shard_collection(self, db_name, coll_name):
        """Shards the given collection."""
        js_shard_coll = '''
            assert.commandWorked(sh.enableSharding("{0}"));
            assert.commandWorked(
                sh.shardCollection("{0}.{1}", {{_id: "hashed"}}));
            db.printShardingStatus();
            '''.format(db_name, coll_name)
        return self.mongoses[0].run_mongo_shell(js_shard_coll)

    def setup_host(self):
        """Ensures necessary files are setup."""
        return (self.config.setup_host() and
                all(shard.setup_host() for shard in self.shards) and
                all(mongos.setup_host() for mongos in self.mongoses))

    def launch(self):
        """Starts the cluster."""
        LOG.info('Launching sharded cluster...')
        if not (self.config.launch() and
                all(shard.launch() for shard in self.shards) and
                all(mongos.launch() for mongos in self.mongoses)):
            return False
        if not self._add_shards():
            return False
        if self.disable_balancer:
            return self.mongoses[0].run_mongo_shell('sh.stopBalancer();')
        return True

    def _add_shards(self):
        """Adds each shard to the cluster."""
        LOG.info('Configuring sharded cluster...')
        # Add shard to mongos
        js_add_shards = []
        for shard in self.shards:
            js_add_shards.append('assert.commandWorked(sh.addShard("{0}"));'.
                                 format(shard.connection_string()))
        if not self.mongoses[0].run_mongo_shell('\n'.join(js_add_shards)):
            LOG.error('Failed to add shards!')
            return False
        # TODO: sharding the ycsb collections or any other collections should
        # be moved to a workload pre-step module. This goes against the design
        # goals of DP 2.0.
        return self.shard_collection('ycsb', 'usertable')

    def destroy(self):
        """Kills the remote custer members."""
        for shard in self.shards:
            shard.destroy()
        self.config.destroy()
        for mongos in self.mongoses:
            mongos.destroy()

    def close(self):
        """Closes SSH connections to remote hosts."""
        for shard in self.shards:
            shard.close()
        self.config.close()
        for mongos in self.mongoses:
            mongos.close()


# NOTE: this is for compatibility with old shell scripts, these will go away
# in favor of reading configuration files.
def get_standalone_opts(storage_engine, host_num=0):
    """Returns a standalone mongod config."""
    return {
        'host': ips.PUBLIC_IPS[host_num],
        'host_private': ips.PRIVATE_IPS[host_num],
        'program_args': {
            'storageEngine': storage_engine
        }
    }


def get_replica_opts(storage_engine, name='rs0', num_nodes=3):
    """Returns replica set config."""
    opts = {
        'name': name,
        'node_opts': []
    }
    for i in range(num_nodes):
        opts['node_opts'].append(get_standalone_opts(storage_engine, i))
    return opts


def get_sharded_opts(storage_engine, num_shards=3, nodes_per_shard=3):
    """Returns a sharded cluster config."""
    cluster_opts = {
        'mongos_opts': [{
            'host': ips.MONGOS_PUBLIC_IP,
            'host_private': ips.MONGOS_PRIVATE_IP
        }],
        'config_opt': {
            'node_opts': []
        },
        'shard_opts': []
    }
    for i in range(3):
        cluster_opts['config_opt']['node_opts'].append({
            'host': ips.CONFIG_PUBLIC_IPS[i],
            'host_private': ips.CONFIG_PRIVATE_IPS[i],
        })
    for i in range(num_shards):
        shard_opts = {
            'node_opts': []
        }
        for j in range(nodes_per_shard):
            node_num = nodes_per_shard * i + j
            shard_opts['node_opts'].append({
                'host': ips.PUBLIC_IPS[node_num],
                'host_private': ips.PRIVATE_IPS[node_num],
                'program_args': {
                    'storageEngine': storage_engine
                }
            })
        cluster_opts['shard_opts'].append(shard_opts)
    return cluster_opts


def start_cluster(cluster_type, storage_engine):
    """Start one of the predefined cluster configurations."""
    cluster = None
    if cluster_type == 'standalone':
        standalone_opts = get_standalone_opts(storage_engine)
        cluster = MongoNode(standalone_opts)
    elif cluster_type == 'single-replica':
        single_replica_opts = get_replica_opts(storage_engine, num_nodes=1)
        cluster = ReplSet(single_replica_opts)
    elif cluster_type == 'replica':
        replica_opts = get_replica_opts(storage_engine)
        cluster = ReplSet(replica_opts)
    elif cluster_type == 'replica-2node':
        # 2 node replica set is the same as 'replica' except the third member
        # is not initially added to the set.
        replica_2node_opts = get_replica_opts(storage_engine)
        replica_2node_opts['node_opts'][2]['add_to_replica'] = False
        cluster = ReplSet(replica_2node_opts)
    elif cluster_type == 'shard':
        cluster_opts = get_sharded_opts(storage_engine)
        cluster = ShardedCluster(cluster_opts)
    else:
        exit('unknown cluster_type')
    # Start the cluster
    if cluster.setup_host() and cluster.launch():
        cluster.close()
    else:
        cluster.destroy()
        cluster.close()
        exit('Failed to start cluster!')


def parse_command_line():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Start a MongoDB cluster in a distributed environment')
    parser.add_argument(
        'cluster_type',
        help='type of cluster to setup')
    parser.add_argument(
        'storage_engine',
        help='storage engine to use')
    parser.add_argument(
        '-d',
        '--debug',
        action='store_true',
        help='enable debug output')
    parser.add_argument(
        '--log-file',
        help='path to log file')
    return parser.parse_args()


def main():
    # import the ips.py file from the current working directory.
    # TODO: Change from hacky import to reading config file
    # ips.py defines PUBLIC_IPS, PRIVATE_IPS, MC_IP, MONGOS_PUBLIC_IP,
    # MONGOS_PRIVATE_IP, CONFIG_PUBLIC_IPS, and CONFIG_PRIVATE_IPS
    global ips
    sys.path.append(os.getcwd())
    import ips
    args = parse_command_line()
    setup_logging(args.debug, args.log_file)
    if not source('setting.sh'):
        exit(1)
    start_cluster(args.cluster_type, args.storage_engine)


if __name__ == '__main__':
    main()
