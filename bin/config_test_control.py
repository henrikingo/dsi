#!/usr/bin/env python2.7
""" Translate DSI configuration file to json file readable by mission control """

from __future__ import print_function

import json
import logging
import sys

import argparse
import yaml

# pylint: disable=relative-import
from common.config import ConfigDict
from common.log import setup_logging

LOG = logging.getLogger(__name__)


def generate_mc_json():
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
    mc_conf['PemFile'] = conf['infrastructure_provisioning']['tfvars']['ssh_key_file']
    ssh_user = conf['infrastructure_provisioning']['tfvars']['ssh_user']

    clients = [ssh_user + '@' + client['public_ip'] for client in
               conf['infrastructure_provisioning']['out']['workload_client']]

    servers = [ssh_user + '@' + server['public_ip'] for server in
               conf['infrastructure_provisioning']['out']['mongod_all']]
    if 'mongos' in conf['infrastructure_provisioning']['out']:
        servers += [ssh_user + '@' + server['public_ip'] for server in
                    conf['infrastructure_provisioning']['out']['mongos']]
    mc_conf['runs'] = []

    for run in conf['test_control']['run']:
        mc_run = {'client_logs': [], 'server_logs': [], 'clients': clients, 'servers': servers}
        mc_run['run_id'] = run['id']
        mc_run['type'] = run['type']
        mc_run['cmd'] = run['cmd']

        if 'background_tasks' in run:
            # Background task defined
            mc_run['background_tasks'] = run['background_tasks'].as_dict()

        mc_conf['runs'].append(mc_run)

        # Create the per run config files
        # I tried testing for existence of the key, byt that did not work
        # properly, so using try catch block.
        try:
            with open(run['config_filename'], 'w') as workloads_file:
                if isinstance(run['workload_config'], dict):
                    workloads_file.write(yaml.dump(run['workload_config'].as_dict()))
                elif isinstance(run['workload_config'], str):
                    workloads_file.write(run['workload_config'])
        except KeyError:
            LOG.warn("No workload config in test control")

    with open('mc.json', 'w') as mc_config_file:
        json.dump(mc_conf, mc_config_file, indent=4, separators=[',', ':'], sort_keys=True)

    # Dump out the config for for the workload. Need to adjust for ycsb Needs to be copied up.


def main(argv):
    ''' Main function. Parse command line options and call generate_mc_json '''
    parser = argparse.ArgumentParser(
        description='Generate control file for mission control from test_control.yml')
    parser.add_argument(
        '-d',
        '--debug',
        action='store_true',
        help='enable debug output')
    parser.add_argument(
        '--log-file',
        help='path to log file')
    args = parser.parse_args(argv)
    setup_logging(args.debug, args.log_file)
    generate_mc_json()

if __name__ == '__main__':
    main(sys.argv[1:])
