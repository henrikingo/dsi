#!/usr/bin/env python2.7
'''Setup an work environment. Copy over the appropriate files.

The long term intention is that this script sets up a working
directory for use with the DP 2.0 operational flow. It will copy in
the appropriate configuration files into the directory, and whatever
other local initialization is needed. All local state will then live
in this directory, while all static content, configuration, and
scripts/executables will be accessed from the DSI repo.

In the short term, this script will copy over the state needed to run
the workflow, matching current reality. As new DP 2.0 features come
online, this script should be updated to pick them up, and to move
towards the long term intention.

'''

from __future__ import print_function
import ConfigParser
import sys
import argparse
import glob
import logging
import os
import os.path
import shutil
import subprocess
import yaml

from common.config import ConfigDict
from common.log import setup_logging

LOGGER = logging.getLogger(__name__)

def read_aws_credentials(config, config_dict):
    '''
    Read AWS credentials into a config object
    '''
    # if we can read variables out of the ~/.aws/credentials file, do so
    read_aws_credentials_file(config)

    # environment variables should supersede config file reading
    read_env_vars(config)
    if 'runtime_secret' in config_dict:
        if 'aws_access_key' in config_dict['runtime_secret']:
            config['aws_access_key'] = config_dict['runtime_secret']['aws_access_key']
        if 'aws_secret_key' in config_dict['runtime_secret']:
            config['aws_secret_key'] = config_dict['runtime_secret']['aws_secret_key']

    if 'aws_access_key' not in config or 'aws_secret_key' not in config:
        LOGGER.critical('AWS credentials not found. Please ensure that they are present in '
                        '~/.aws/credentials or are present in your environment as AWS_ACCESS_KEY_ID'
                        'and AWS_SECRET_ACCESS_KEY.')
        assert False

def read_aws_credentials_file(config):
    '''
    Read AWS credentials from the 'default' field of ~/.aws/credentials, if it exists
    '''
    defaults = {}
    credential_path = os.path.expanduser('~/.aws/credentials')
    section = 'default'
    config_parser = ConfigParser.ConfigParser(defaults=defaults)
    config_parser.read(credential_path)
    if config_parser.has_section(section):
        config['aws_access_key'] = config_parser.get(section, 'aws_access_key_id')
        config['aws_secret_key'] = config_parser.get(section, 'aws_secret_access_key')
    return config

def read_env_vars(config):
    '''
    Read AWS access key id and and secret access key from environment variables
    '''
    if 'AWS_ACCESS_KEY_ID' in os.environ:
        config['aws_access_key'] = os.environ.get('AWS_ACCESS_KEY_ID')
    if 'AWS_SECRET_ACCESS_KEY' in os.environ:
        config['aws_secret_key'] = os.environ.get('AWS_SECRET_ACCESS_KEY')
    return config

def parse_command_line(config, args=None):
    #pylint: disable=line-too-long,too-many-branches
    '''
    Parse the command line options for setting up a working directory
    '''

    parser = argparse.ArgumentParser(description='Setup DSI working environment. For instructions \
                    on setting up dsi locally, see \
                    https://drive.google.com/open?id=14QXOmo-ia8w72pW5zqQ2fCWfXEwiVQ8_1EoMCkB4baY')

    # These command line options support current configuration. It
    # should eventually support selecting the appropriate files for
    # infrastructure.yml, mongodb_setup.yml, test_control.yml, and
    # analyis.yml. The options should be reviewed as the different
    # units start to use the config file, with new command line
    # options added as needed, and old options removed.
    #
    # For example, the --cluster-type option currently affects the
    # infrastructure provisioning and mongodb provisioning
    # steps. Eventually that option should be removed, and replaced
    # with distinct options for selecting infrastructure provisioning
    # options and mongodb setup options.
    parser.add_argument('-b',
                        '--bootstrap-file',
                        help='Path to bootstrap.yml')
    parser.add_argument('-d',
                        '--debug',
                        action='store_true',
                        help='enable debug output')
    parser.add_argument('--directory',
                        default='.',
                        help="Directory to setup. Defaults to current directory")
    parser.add_argument('--log-file',
                        help='path to log file')

    # This option is ignored but allowed for backward compatibility
    parser.add_argument('--production',
                        action='store_true',
                        default=False,
                        help='Indicate the script is being called as part of a production run. '
                        'This suppresses certain messages appropriate for local runs (Ignored).')
    parser.add_argument('-v',
                        '--verbose',
                        action='store_true',
                        help='Enable verbose output')
    args = parser.parse_args(args)

    setup_logging(args.debug, args.log_file)  # pylint: disable=no-member

    if args.bootstrap_file:
        config['bootstrap_file'] = args.bootstrap_file
    if args.directory:
        config['directory'] = args.directory
    return config

def copy_config_files(dsipath, config, directory):
    '''
    Copy all related config files to the target directory
    '''
    # Pairs of ConfigDict module, and bootstrap.yml input.
    # This is all the variable info needed to build the from and to file paths down below.
    configs_to_copy = {"infrastructure_provisioning": config.get("infrastructure_provisioning", ""),
                       "mongodb_setup": config.get("mongodb_setup", ""),
                       "test_control": config.get("test_control", "")}

    for config_module, bootstrap_variable in configs_to_copy.iteritems():
        # Example: ./mongodb_setup.yml
        target_file = os.path.join(directory, config_module + ".yml")
        # Example: ../dsi/configurations/mongodb_setup/mongodb_setup.standalone.wiredTiger.yml
        source_file = os.path.join(dsipath,
                                   "configurations",
                                   config_module,
                                   config_module + "." + bootstrap_variable + ".yml")

        #pylint: disable=broad-except
        try:
            shutil.copyfile(source_file, target_file)
            LOGGER.debug("Copied " + source_file + " to work directory %s.", target_file)
        except Exception as error:
            # If a source file doesn't exist, it's probably because a wrong or no option was
            # provided in bootstrap.yml. When running manually, this is not fatal. For example,
            # user may want to manually copy some files from somewhere else
            error_str = "Failed to copy {} from {}.\nError: {}".format(target_file,
                                                                       source_file,
                                                                       str(error))
            if config["production"]:
                LOGGER.critical(error_str)
                raise
            else:
                LOGGER.warn(error_str)

    return

def setup_overrides(config, directory):
    '''
    Generate the overrides.yml file

    Note: this only happens when running locally, outside of evergreen. In evergreen runs,
    the relevant variables are set in infrastructure_provisioning.yml and should not be present in
    config at this point.
    '''

    overrides = {}
    override_path = os.path.join(directory, 'overrides.yml')
    tfvars = {}
    if 'ssh_key_file' in config:
        tfvars['ssh_key_file'] = config['ssh_key_file']
    if 'ssh_key_name' in config:
        tfvars['ssh_key_name'] = config['ssh_key_name']
    if 'owner' in config:
        tfvars['tags'] = {'owner': config['owner']}
    if os.path.exists(override_path):
        with open(override_path) as override_file:
            overrides = yaml.load(override_file)
    overrides.update({'infrastructure_provisioning':
                      {'tfvars': tfvars}})
    with open(override_path, 'w') as override_file:
        override_file.write(yaml.dump(overrides, default_flow_style=False))


def setup_security_tf(config, directory):
    '''
    Generate the security.tf file
    '''
    # config doesn't include options from infrastructure_provisioning.yml,
    # because at the start of bootstrap.py, when we read input options with
    # ConfigDict, it wasn't present.
    # This method should be moved to infrastructure_provisioning.py.
    # In the mean time we just hard code the values used in evergreen.
    if 'ssh_key_name' not in config:
        config['ssh_key_name'] = 'serverteam-perf-ssh-key'
        LOGGER.warn("Using default SSH key name from defaults.yml. "
                    "Please ensure that your own SSH key is being used.")
    if 'ssh_key_file' not in config:
        config['ssh_key_file'] = 'aws_ssh_key.pem'
        LOGGER.warn("Using default SSH key file from defaults.yml. "
                    "Please ensure that your own SSH key is being used.")
    # Write security.tf. Used to be done by make_terraform_env.sh
    with open(os.path.join(directory, 'security.tf'), 'w') as security:
        security.write('provider "aws" {\n')
        security.write('    access_key = "{0}"\n'.format(config['aws_access_key']))
        security.write('    secret_key = "{0}"\n'.format(config['aws_secret_key']))
        security.write('    region = "${var.region}"\n')
        security.write('}\n')
        security.write('variable "key_name" {\n')
        security.write('    default = "{0}"\n'.format(config['ssh_key_name']))
        security.write('}\n')
        security.write('variable "key_file" {\n')
        security.write('    default = "{0}"\n'.format(config['ssh_key_file']))
        security.write('}')


def find_terraform(config, directory):
    '''
    Returns the location of the terraform binary to use
    '''
    try:
        system_tf = subprocess.check_output(['which', 'terraform']).strip()
    except subprocess.CalledProcessError:
        system_tf = None

    if 'terraform' in config:
        terraform = os.path.abspath(os.path.expanduser(config['terraform']))
        LOGGER.debug('Using terraform binary specified by '
                     'bootstrap.terraform %s', config['terraform'])
    elif system_tf is not None:
        terraform = os.path.abspath(system_tf)
        LOGGER.debug('Using terraform binary specified by $(which terraform)')
    else:
        terraform = os.path.join(directory, 'terraform')
        LOGGER.debug('Using terraform binary in default location')

    LOGGER.info('Path to terraform binary is %s', terraform)
    return terraform

def validate_terraform(config):
    '''Asserts that terraform is the correct version'''
    if not config['production']:
        try:
            version = subprocess.check_output([config['terraform'], "version"]).split('\n')[0]
        except subprocess.CalledProcessError as error:
            if error.returncode == 1:
                LOGGER.critical("Call to terraform failed.")
            if error.returncode == 126:
                LOGGER.critical("Cannot execute terraform binary file.")
            if error.returncode == 127:
                LOGGER.critical("No terraform binary file found.")
            LOGGER.critical("See documentation for installing terraform: http://bit.ly/2ufjQ0R")
            assert False
        if not version == config['terraform_version_check']:
            LOGGER.critical('You are using %s, but DSI requires %s.',
                            version, config['terraform_version_check'])
            LOGGER.critical("See documentation for installing terraform: http://bit.ly/2ufjQ0R")
            assert False

def find_mission_control(config, dsipath):
    '''
    Returns the location of the mission_control binary to use.
    '''
    try:
        system_mc = subprocess.check_output(['which', 'mc']).strip()
    except subprocess.CalledProcessError:
        system_mc = None

    if 'mc' in config:
        mission_control = os.path.abspath(os.path.expanduser(config['mc']))
        LOGGER.debug('Using mission-control binary specified by bootstrap.mc %s', config['mc'])
    elif system_mc is not None:
        mission_control = os.path.abspath(system_mc)
        LOGGER.debug('Using mission-control binary specified by $(which mc)')
    else:
        mission_control = os.path.join(dsipath, "bin/mc")
        LOGGER.debug('Using mission-control binary in default location')

    LOGGER.info('Path to mission-control binary is %s', mission_control)
    return mission_control

def validate_mission_control(config):
    '''Asserts that mission-control is on the path'''
    if not config['production']:
        try:
            errors = subprocess.Popen(["mc", "-h"],
                                      stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE).communicate()[1]
            if errors.split('\n')[0] != 'Usage of mc:':
                LOGGER.critical('Call to mission-control failed.')
                LOGGER.critical('See documentation for installing '
                                'mission-control: http://bit.ly/2ufjQ0R')
                assert False
        except OSError:
            LOGGER.critical('mission-control binary file not found.')
            LOGGER.critical('See documentation for installing '
                            'mission-control: http://bit.ly/2ufjQ0R')
            assert False

def write_dsienv(directory, dsipath, mission_control, terraform, config):
    '''
    Writes out the dsienv.sh file. It saves the path to DSI repo.
    '''
    with open(os.path.join(directory, 'dsienv.sh'), 'w') as dsienv:
        dsienv.write('export DSI_PATH={0}\n'.format(dsipath))
        dsienv.write('export PATH={0}/bin:$PATH\n'.format(dsipath))
        dsienv.write('export MC={0}\n'.format(mission_control))
        dsienv.write('export TERRAFORM={0}'.format(terraform))
        if "workloads_dir" in config:
            dsienv.write('\nexport WORKLOADS_DIR={0}'.format(config["workloads_dir"]))
        if "ycsb_dir" in config:
            dsienv.write('\nexport YCSB_DIR={0}'.format(config["ycsb_dir"]))

def load_bootstrap(config, directory):
    '''
    Move specified bootstrap.yml file to correct location for read_runtime_values
    '''
    # Create directory if it doesn't exist
    if not os.path.exists(directory):
        os.makedirs(directory)

    if 'bootstrap_file' in config:
        bootstrap_path = os.path.abspath(os.path.expanduser(config['bootstrap_file']))
        if os.path.isfile(bootstrap_path):
            if not bootstrap_path == os.path.abspath(os.path.join(directory, 'bootstrap.yml')):
                if os.path.isfile(os.path.abspath(os.path.join(directory, 'bootstrap.yml'))):
                    LOGGER.critical('Attempting to overwrite existing bootstrap.yml file in %s. '
                                    'Aborting.', directory)
                    assert False
                shutil.copyfile(bootstrap_path, os.path.join(directory, 'bootstrap.yml'))
        else:
            LOGGER.critical("Location specified for bootstrap.yml is invalid.")
            assert False
    else:
        bootstrap_path = os.path.abspath(os.path.expanduser(os.path.join(os.getcwd(),
                                                                         'bootstrap.yml')))
        if os.path.isfile(bootstrap_path):
            if not bootstrap_path == os.path.abspath(os.path.join(directory, 'bootstrap.yml')):
                if os.path.isfile(os.path.abspath(os.path.join(directory, 'bootstrap.yml'))):
                    LOGGER.critical('Attempting to overwrite existing bootstrap.yml file in %s. '
                                    'Aborting.', directory)
                    assert False
                shutil.copyfile(bootstrap_path, os.path.join(directory, 'bootstrap.yml'))

    current_path = os.getcwd()
    os.chdir(directory)
    config_dict = ConfigDict('bootstrap')
    config_dict.load()
    for key in config_dict['bootstrap'].keys():
        config[key] = config_dict['bootstrap'][key]

    # terraform required_version must be specified, we fail hard if user has tried to unset
    config['terraform_version_check'] = \
        config_dict['infrastructure_provisioning']['terraform']['required_version']

    os.chdir(current_path)

    return config_dict

def main():
    ''' Main function for setting up working directory
    '''

    config = {}
    parse_command_line(config)
    directory = os.path.abspath(os.path.expanduser(config['directory']))
    LOGGER.info('Creating work directory in: %s', directory)

    if os.path.exists(os.path.join(directory, 'dsienv.sh')):
        print ("It looks like you have already setup "
               "{0} for dsi. dsienv.sh exists. Stopping".format(directory))
        sys.exit(1)

    # Copies bootstrap.yml if necessary and then reads values into config
    config_dict = load_bootstrap(config, directory)
    read_aws_credentials(config, config_dict)

    # Compute DSI Path based on directory location of this script. Go up one level
    dsipath = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    LOGGER.info('dsipath is %s', dsipath)

    mission_control = find_mission_control(config, dsipath)
    config['terraform'] = find_terraform(config, directory)
    validate_mission_control(config)
    validate_terraform(config)

    write_dsienv(directory, dsipath, mission_control, config['terraform'], config)

    # Copy terraform tf files and remote-scripts to work directory
    cluster_path = os.path.join(dsipath, 'clusters', 'default')
    remote_scripts_path = os.path.join(dsipath, 'clusters', 'remote-scripts')
    LOGGER.debug('Cluster path is %s', cluster_path)
    for filename in glob.glob(os.path.join(cluster_path, '*')):
        shutil.copy(filename, directory)
        LOGGER.debug("Copied %s to work directory %s.", filename, directory)

    remote_scripts_target = os.path.join(directory, 'remote-scripts')
    LOGGER.debug("remote_scripts_target is %s", remote_scripts_target)
    LOGGER.debug("remote_scripts_path is %s", remote_scripts_path)
    os.mkdir(remote_scripts_target)
    for filename in glob.glob(os.path.join(remote_scripts_path, '*')):
        shutil.copy(filename, remote_scripts_target)

    # copy modules
    modules_path = os.path.join(dsipath, 'clusters', 'modules')
    modules_target = os.path.join(directory, 'modules')
    shutil.copytree(modules_path, modules_target)

    # copy necessary config files to the current directory
    copy_config_files(dsipath, config, directory)

    # This writes an overrides.yml with the ssh_key_file, ssh_key_name and owner, if given in
    # bootstrap.yml.
    setup_overrides(config, directory)

    setup_security_tf(config, directory)

    LOGGER.info("Local environment setup in %s", directory)

if __name__ == '__main__':
    main()
