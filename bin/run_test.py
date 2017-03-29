#!/usr/bin/env python2.7
""" Test runner in DSI Framework """

from __future__ import print_function
import argparse
import copy
import logging
import os
import shutil
import subprocess
import sys

# pylint: disable=relative-import
from common.config import ConfigDict
from common.host import execute_list
from common.log import setup_logging
import config_test_control

LOG = logging.getLogger(__name__)

def setup_ssh_agent(config):
    ''' Setup the ssh-agent, and update our environment for it.

    :param ConfigDict config: The system configuration
    '''

    ssh_agent_info = subprocess.check_output(['ssh-agent', '-s'])
    # This expansion updates our environment by parsing the info from the previous line
    # It splits the data into lines, and then for any line of the form
    # "key=value", adds {key: value} to the environment
    os.environ.update(dict([line.split('=') for line in ssh_agent_info.split(';') if '=' in line]))
    subprocess.check_call(['ssh-add',
                           config['infrastructure_provisioning']['tfvars']['ssh_key_file']])

def cleanup_reports():
    ''' Clean up reports directory and files '''
    if os.path.exists('reports'):
        shutil.rmtree('reports')
    if os.path.exists('../reports.tgz'):
        os.remove('../reports.tgz')

def copy_perf_output():
    ''' Put perf.json in the correct place'''
    if os.path.exists('../perf.json'):
        os.remove('../perf.json')
    shutil.copyfile('perf.json', '../perf.json')

    # Read perf.json into the log file
    with open('../perf.json') as perf_file:
        for line in perf_file:
            LOG.info(line)


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

    config = ConfigDict('test_control')
    config.load()
    test_control = config['test_control']

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

    setup_ssh_agent(config)
    cleanup_reports()

    # Execute pre task steps
    if 'pre_task' in test_control:
        execute_list(test_control['pre_task'], config)

    # Go through the existing scripts if necessary
    if args.test == 'initialSync':
        subprocess.check_call([os.path.join(dsi_bin_path, 'run-initialSync.sh'),
                               args.storage_engine, args.test, args.cluster])
    else:
        # Everything should eventually come through this path
        # Call mission control
        # Pass in MC_MONITOR_INTERVAL=config.test_control.mc_monitor_interval to environment
        env = copy.deepcopy(os.environ)
        env['MC_MONITOR_INTERVAL'] = str(config['test_control']['mc']['monitor_interval'])
        env['MC_PER_THREAD_STATS'] = str(config['test_control']['mc']['per_thread_stats'])
        LOG.debug('env for mc call is %s', str(env))
        subprocess.check_call([mission_control,
                               '-config',
                               'mc.json',
                               '-run',
                               args.test,
                               '-o',
                               'perf.json'], env=env)

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
        try: # We've run the test. Don't stop on error
            execute_list(test_control['post_task'], config)
        except Exception as exception: #pylint: disable=broad-except
            LOG.error("Caught an exception in post_task step. %s", str(exception))
    # Set perf.json to 555
    # Todo: replace with os.chmod call or remove in general
    # Previously this was set to 777. I can't come up with a good reason.
    subprocess.check_call(['chmod', '555', 'perf.json'])

    copy_perf_output()

if __name__ == '__main__':
    main(sys.argv[1:])
