#!/usr/bin/env python2.7
""" Test runner in DSI Framework """

from __future__ import print_function
import argparse
import logging
import os.path
import subprocess
import sys

# pylint: disable=relative-import
from common.config import ConfigDict
from common.host import execute_list
from common.log import setup_logging
import config_test_control

LOG = logging.getLogger(__name__)

def main(argv):
    ''' Main function. Parse command line options, and run tests '''
    parser = argparse.ArgumentParser(description='DSI Test runner')
    # All the positional arguments to go away when config dict used
    # properly. Here now to match existing call.
    parser.add_argument('storage_engine', help="mmapv1 or wiredTiger")
    parser.add_argument('test', help='The test type to run. This will eventually go away')
    parser.add_argument('cluster', help='The cluster type')
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

    conf = ConfigDict('test_control')
    conf.load()
    test_control = conf['test_control']

    dsi_bin_path = os.path.join(os.path.dirname(os.path.abspath(__file__)))

    # This path should probably be in the config path somewhere rather
    # than the environemnt. setup_work_env.py can set it up
    # From CR comment: In that case it should be in bootstrap.out.yml, since it is an output of
    # that module.
    mission_control = os.path.join(dsi_bin_path, 'mc')
    if 'MC' in os.environ:
        mission_control = os.environ['MC']

    # While we are still using MC
    config_test_control.generate_mc_json()

    # Setup paramiko agent

    # Execute pre task steps
    if 'pre_task' in test_control:
        execute_list(test_control['pre_task'], conf)

    # Go through the existing scripts if necessary
    if args.test in ['core', 'non_sharded', 'secondary_performance', 'mongos', 'move_chunk']:
        subprocess.check_call([os.path.join(dsi_bin_path, 'run-benchRun.sh'),
                               args.storage_engine, args.test, args.cluster])
    elif args.test in ['ycsb']:
        subprocess.check_call([os.path.join(dsi_bin_path, 'run-ycsb.sh'), args.storage_engine,
                               args.test, args.cluster])
    elif args.test == 'initialSync':
        subprocess.check_call([os.path.join(dsi_bin_path, 'run-initialSync.sh'),
                               args.storage_engine, args.test, args.cluster])
    elif args.test == 'initialSync-logkeeper':
        subprocess.check_call([os.path.join(dsi_bin_path, 'run-initialSync-logkeepr.sh'),
                               args.storage_engine, args.test, args.cluster])
    else:
        # Everything should eventually come through this path
        # Call mission control
        subprocess.check_call([mission_control,
                               '-i',
                               conf['infrastructure_provisioning']['tfvars']['ssh_key_file'],
                               '-config',
                               'mc.json',
                               '-run',
                               args.test, # This doesn't match the special case in run scripts.
                                          # I'm not sure it matetrs.
                               '-o',
                               'perf.json'])

        # Next step in refactoring: Call mission control per run, and
        # only do one run per call to mission control. That will allow
        # us to do the pre and post-run steps in here.

        # for run in test_control:
        #     # execute pre_runsteps
        #     if 'pre_run' in test_control:
        #         execute_list(test_control['pre_run'], conf)
        #     if 'pre_run' in run: # This is a run specific thing to run before the run
        #         execute_list(run['pre_run'], conf)

        #     # Generate the mc.json file for this run only. Save it to unique name
        #     config_test_control.generate_mc_json(run)
        #     # Move MC call here. perf.jsons must be combined.

        #     # Execute the post_run_steps
        #     if 'post_run' in run:
        #         execute_list(run['post_run'], conf)
        #     if 'post_run' in test_control:
        #         execute_list(test_control['post_run'], conf)

    # Execute post task steps
    if 'post_task' in test_control:
        execute_list(test_control['post_task'], conf)


if __name__ == '__main__':
    main(sys.argv[1:])
