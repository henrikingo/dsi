#!/usr/bin/env python2.7
""" Translate DSI configuration file to json file readable by mission control """

from __future__ import print_function

import json
import logging
import os
import sys

import argparse
import yaml

from common.config import ConfigDict
from common.log import setup_logging

LOG = logging.getLogger(__name__)


def generate_mc_json(test_index=0):
    ''' Generate a json config file for mission control '''

    conf = ConfigDict('test_control')
    conf.load()
    mc_conf = {}

    # NOTE: MC will NOT run DB correctness checks if the jstests_dir
    # parameter is not present in the mc.json.  This is the path to DB
    # correctness JS tests, to be run at the end of a task.
    try:
        mc_conf['jstests_dir'] = conf['test_control']['jstests_dir']
    except KeyError:
        LOG.warn("No jstests_dir found in test_control")

    # New path for reading in the ssh_user and ssh_key_file values
    ssh_key_file = conf['infrastructure_provisioning']['tfvars']['ssh_key_file']
    ssh_key_file = os.path.expanduser(ssh_key_file)
    mc_conf['PemFile'] = ssh_key_file
    ssh_user = conf['infrastructure_provisioning']['tfvars']['ssh_user']

    clients = [
        ssh_user + '@' + client['public_ip']
        for client in conf['infrastructure_provisioning']['out']['workload_client']
    ]

    servers = [
        ssh_user + '@' + server['public_ip']
        for server in conf['infrastructure_provisioning']['out']['mongod']
    ]
    if 'mongos' in conf['infrastructure_provisioning']['out']:
        servers += [
            ssh_user + '@' + server['public_ip']
            for server in conf['infrastructure_provisioning']['out']['mongos']
        ]

    test = conf['test_control']['run'][test_index]

    mc_test = {'client_logs': [], 'server_logs': [], 'clients': clients, 'servers': servers}
    mc_test['run_id'] = test['id']
    mc_test['type'] = test['type']
    mc_test['cmd'] = test['cmd']
    mc_conf['runs'] = [mc_test]

    try:
        workload_config = test['workload_config']
        with open(test['config_filename'], 'w') as workloads_file:
            if isinstance(workload_config, dict):
                # Can't assign into config dict. Need an actual dictionary
                workload_config_dict = workload_config.as_dict()
                if 'scale_factor' in workload_config_dict:
                    if isinstance(workload_config_dict['scale_factor'], str):
                        #pylint: disable=eval-used
                        workload_config_dict['scale_factor'] = eval(
                            workload_config_dict['scale_factor'])
                workloads_file.write(yaml.dump(workload_config_dict))
            elif isinstance(workload_config, str):
                workloads_file.write(workload_config)
    except KeyError:
        LOG.warn("No workload config in test control")

    # Dump out the config for for the workload. Need to adjust for ycsb Needs to be copied up.
    with open('mc_' + test['id'] + '.json', 'w') as mc_config_file:
        json.dump(mc_conf, mc_config_file, indent=4, separators=[',', ':'], sort_keys=True)


def main(argv):
    ''' Main function. Parse command line options and call generate_mc_json '''
    parser = argparse.ArgumentParser(
        description='Generate control file for mission control from test_control.yml')
    parser.add_argument('-d', '--debug', action='store_true', help='enable debug output')
    parser.add_argument('--log-file', help='path to log file')
    args = parser.parse_args(argv)
    setup_logging(args.debug, args.log_file)
    generate_mc_json()


if __name__ == '__main__':
    main(sys.argv[1:])
