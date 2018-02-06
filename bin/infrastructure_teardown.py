#!/usr/bin/env python
""""
Teardown AWS resources using terraform.
It is important this python file can be used without any dependencies on our own other python files
since in one of the cases the script is used, it is isolated from the other python files. This
occurs when it is used from within the Evergreen data directory which stores terraform state.
Furthermore, this file does not have any pip package dependencies.

"""
import argparse
import glob
import logging
import os
import shutil
import subprocess
from subprocess import CalledProcessError

LOG = logging.getLogger(__name__)


def destroy_resources():
    """ Destroys AWS resources using terraform """
    teardown_script_path = os.path.dirname(os.path.abspath(__file__))
    previous_directory = None
    terraform = None
    if glob.glob(teardown_script_path + '/provisioned.*'):
        previous_directory = os.getcwd()
        os.chdir(teardown_script_path)

    if "TERRAFORM" in os.environ:
        terraform = os.environ['TERRAFORM']
    else:
        terraform = './terraform'

    var_file = ''
    if os.path.isfile('cluster.json'):
        var_file = '-var-file=cluster.json'
    else:
        LOG.critical("In infrastructure_teardown.py and cluster.json does not exist. Giving up.")
        if previous_directory is not None:
            os.chdir(previous_directory)
        raise (UserWarning(
            "In infrastructure_teardown.py and cluster.json does not exist. Giving up."))

    try:
        # Destroy instances first.
        subprocess.check_call([terraform, 'destroy', var_file, '-force', '-target=module.cluster'])
        # Then destroy the rest, which is the placement group.
        # This is a workaround for the fact that depends_on doesn't work with modules.
        subprocess.check_call([terraform, 'destroy', var_file, '-force'])
    except CalledProcessError:
        LOG.info('Failed destroying resources, retrying')
        subprocess.check_call([terraform, 'destroy', var_file, '-force'])
    if previous_directory is not None:
        os.chdir(previous_directory)

    # Hard coding, since we cannot use ConfigDict yet. (PERF-1241 and TODO PERF-1298 to remove)
    evg_data_dir = "/data/infrastructure_provisioning"
    LOG.info("Cleaning up %s", evg_data_dir)
    if os.path.exists(evg_data_dir):
        shutil.rmtree(evg_data_dir)


def parse_command_line():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Destroy EC2 instances on AWS using terraform.')
    parser.add_argument('--log-file', help='path to log file')
    parser.add_argument('-d', '--debug', action='store_true', help='enable debug output')
    args = parser.parse_args()
    return args


def setup_logging(verbose, filename=None):
    """
    Copied over from common.log due to isolation of this script.
    Configure logging verbosity and destination.
    """
    loglevel = logging.DEBUG if verbose else logging.INFO
    handler = logging.FileHandler(filename) if filename else logging.StreamHandler()
    handler.setLevel(loglevel)
    handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
    root_logger = logging.getLogger()
    root_logger.setLevel(loglevel)
    root_logger.addHandler(handler)


def main():
    """ Main Function """
    args = parse_command_line()
    setup_logging(args.debug, args.log_file)
    destroy_resources()


if __name__ == '__main__':
    main()
