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
import copy
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

DEFAULT_CONFIG = {'infrastructure_provisioning': 'single',
                  'aws_access_key': 'NoAccessKey',
                  'aws_secret_key': "NoSecretKey",
                  'directory': '.',
                  'production': False,
                  # These are just used as the default values for security.tf file, overriden at
                  # runtime in infrastructure_provisioning.yml -> cluster.json
                  'ssh_key_name': 'serverteam-perf-ssh-key',
                  'ssh_key_file': 'aws_ssh_key.pem',
                 }


def build_config(args=None):
    '''
    Build a config object, including the specified arguments
    '''
    # default values for config
    config = copy.copy(DEFAULT_CONFIG)

    # if we can read variables out of the ~/.aws/credentials file, do so
    read_aws_creds(config)

    # if we are running this on evergreen, use the runtime values as defaults
    read_runtime_values(config)

    # environment variables should supersede config file reading
    read_env_vars(config)

    # command-line options should supersede env vars and cred file
    parse_command_line(config, args)

    return config

def read_runtime_values(config):
    '''
    Read default config values from the 'bootstrap' and 'runtime' ConfigDict modules
    '''
    config_dict = ConfigDict('bootstrap')
    config_dict.load()
    for key in config_dict['bootstrap'].keys():
        config[key] = config_dict['bootstrap'][key]

    if 'runtime_secret' in config_dict:
        if 'aws_access_key' in config_dict['runtime_secret']:
            config['aws_access_key'] = config_dict['runtime_secret']['aws_access_key']
        if 'aws_secret_key' in config_dict['runtime_secret']:
            config['aws_secret_key'] = config_dict['runtime_secret']['aws_secret_key']

def read_aws_creds(config):
    '''
    Read AWS credentials from the 'default' field of ~/.aws/credentials, if it exists
    '''
    defaults = {}
    credential_path = os.path.expanduser('~/.aws/credentials')
    section = 'default'
    config_parser = ConfigParser.ConfigParser(defaults=defaults)
    config_parser.read(credential_path)
    if config_parser.has_section(section):
        config['aws_access_key'] = config_parser.get('default', 'aws_access_key_id')
        config['aws_secret_key'] = config_parser.get('default', 'aws_secret_access_key')
    return config

def read_env_vars(config):
    '''
    Read AWS access key id and and secret access key from environment variables
    '''
    if 'AWS_ACCESS_KEY_ID' in os.environ:
        config['aws_access_key'] = os.environ.get('AWS_ACCESS_KEY_ID',
                                                  DEFAULT_CONFIG['aws_access_key'])
    if 'AWS_SECRET_ACCESS_KEY' in os.environ:
        config['aws_secret_key'] = os.environ.get('AWS_SECRET_ACCESS_KEY',
                                                  DEFAULT_CONFIG['aws_access_key'])
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
    parser.add_argument('-k',
                        '--aws-access-key',
                        help="AWS api access key. If this flag is not used, the key name will \
                        default to $AWS_ACCESS_KEY_ID if set, then to the evergreen expansion \
                        ${aws_access_key} if set in runtime.yml, then to the access key specified \
                        in [default] section of ~/.aws/credentials, and 'NoAccessKey' otherwise.")
    parser.add_argument('--aws-key-name',
                        help='Synonym for --aws-access-key. (Deprecated)')
    parser.add_argument('-s',
                        '--aws-secret-file',
                        help="File containing AWS secret. If this flag is not used, the secret \
                        will default to $AWS_SECRET_ACCESS_KEY if set, then to the \
                        evergreen expansion ${aws_secret_key} if set in runtime.yml, then to the \
                        secret specified in the [default] section of ~/.aws/credentials, and \
                        'NoSecret' otherwise.")
    # To be replaced by infrastructure.yml selection option
    parser.add_argument('-c',
                        '--cluster-type',
                        help='Set the cluster type. Defaults to the evergreen expansion ${cluster} \
                        if set in runtime.yml, and to \'single\' otherwise.')
    parser.add_argument('--config',
                        action='append',
                        help='Config file to load. Can be called multiple times and combined.'\
                        'On conflicts the last file on the command line wins')
    parser.add_argument('-d',
                        '--debug',
                        action='store_true',
                        help='enable debug output')
    parser.add_argument('--directory',
                        help="Directory to setup. Defaults to current directory")
    parser.add_argument('--log-file',
                        help='path to log file')
    parser.add_argument('--mc',
                        help='The path of the mc executable. Defaults to $(which mc) if mc is \
                        in the PATH, and to $DSI_PATH/bin/mc if not.')
    parser.add_argument('--owner',
                        help='Owner tag for AWS resources')
    parser.add_argument('--ssh-keyfile-path',
                        help="Synonym to --ssh-key-file")
    parser.add_argument('-p',
                        '--ssh-key-file',
                        help="Path to AWS ssh key file (pem)")
    parser.add_argument('--ssh-key',
                        help="Synonym for --ssh-key-name. (Deprecated)")
    parser.add_argument('--ssh-key-name',
                        help="The name (in EC2) of the SSH key to use.")
    parser.add_argument('--terraform',
                        help='The path of the terraform executable. Defaults to $(which terraform) \
                        if terraform is in the path, and to <directory>/terraform if not. For \
                        terraform <=0.6.x, the terraform provider binaries are expected to be in \
                        the same directory.')
    parser.add_argument('--production',
                        action='store_true',
                        help='Indicate the script is being called as part of a production run. '
                        'This suppresses certain messages appropriate for local runs')
    parser.add_argument('-v',
                        '--verbose',
                        action='store_true',
                        help='Enable verbose output')
    args = parser.parse_args(args)

    # TODO: This is now very late in the execution, needs to be moved earlier.
    setup_logging(args.debug, args.log_file)  # pylint: disable=no-member

    if args.config:
        for conf in args.config:
            config.update(yaml.load(open(conf)))
    # Temporary fix for cluster_type, will be removed in subsequent ticket
    if args.cluster_type:
        config['infrastructure_provisioning'] = args.cluster_type
    if args.aws_key_name:
        config['aws_access_key'] = args.aws_key_name
    if args.aws_access_key:
        config['aws_access_key'] = args.aws_access_key
    if args.ssh_keyfile_path:
        config['ssh_key_file'] = args.ssh_keyfile_path
    if args.ssh_key_file:
        config['ssh_key_file'] = args.ssh_key_file
    if args.ssh_key:
        config['ssh_key_name'] = args.ssh_key
    if args.ssh_key_name:
        config['ssh_key_name'] = args.ssh_key_name
    if args.directory:
        config['directory'] = args.directory
    if args.owner:
        config['owner'] = args.owner
    if args.aws_secret_file:
        config['aws_secret_file'] = args.aws_secret_file
    if args.production:
        config['production'] = True
    if args.mc:
        config['mc'] = args.mc
    if args.terraform:
        config['terraform'] = args.terraform
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
        LOGGER.debug('Using terraform binary specified by --terraform %s', config['terraform'])
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
            version = subprocess.check_output(["terraform", "version"]).split('\n')[0]
        except subprocess.CalledProcessError as error:
            if error.returncode == 1:
                LOGGER.critical("Call to terraform failed.")
            if error.returncode == 126:
                LOGGER.critical("Cannot execute terraform binary file.")
            if error.returncode == 127:
                LOGGER.critical("No terraform binary file found.")
            LOGGER.critical("See documentation for installing terraform: http://bit.ly/2ufjQ0R")
            assert False
        if not version == "Terraform v0.9.11":
            version_error = "You are using {0}, but DSI requires Terraform v0.9.11.".format(version)
            LOGGER.critical(version_error)
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
        LOGGER.debug('Using mission-control binary specified by --mc %s', config['mc'])
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

def main():
    ''' Main function for setting up working directory
    '''

    config = build_config()
    directory = os.path.abspath(os.path.expanduser(config['directory']))
    LOGGER.info('Creating work directory in: %s', directory)

    if os.path.exists(os.path.join(directory, 'dsienv.sh')):
        print ("It looks like you have already setup "
               "{0} for dsi. dsienv.sh exists. Stopping".format(directory))
        sys.exit(1)

    # Compute DSI Path based on directory location of this script. Go up one level
    dsipath = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    LOGGER.info('dsipath is %s', dsipath)

    mission_control = find_mission_control(config, dsipath)
    terraform = find_terraform(config, directory)
    validate_mission_control(config)
    validate_terraform(config)

    # Create directory if it doesn't exist
    if not os.path.exists(directory):
        os.makedirs(directory)

    if directory != os.getcwd() and os.path.isfile('bootstrap.yml'):
        shutil.copyfile('bootstrap.yml', os.path.join(directory, 'bootstrap.yml'))

    write_dsienv(directory, dsipath, mission_control, terraform, config)

    # TODO: Copy of persisted terraform information should be copied
    # into working directory here. This is future work to support tying
    # the terraform cluster to the evergreen runner.


    # if we specified a secret file, use its contents as the aws secret
    if 'aws_secret_file' in config:
        # Read in the secret
        config['aws_secret'] = open(config['aws_secret_file']).read().rstrip()

    # Todo: This section should be replaced by code to select infrastructure.yml
    cluster_path = os.path.join(dsipath, 'clusters', config['infrastructure_provisioning'])
    remote_scripts_path = os.path.join(dsipath, 'clusters', 'remote-scripts')
    # Copy over all files from cluster directory
    if not os.path.isdir(cluster_path):
        cluster_path = os.path.join(dsipath, 'clusters', 'default')
    LOGGER.debug('Cluster path is %s', cluster_path)
    for filename in glob.glob(os.path.join(cluster_path, '*')):
        shutil.copy(filename, directory)
        LOGGER.debug("Copied %s to work directory %s.", filename, directory)

    # Copy over all files from the remote scripts directory Note that
    # this is copying above the workload directory for now. This is
    # suboptimal and should be changed in the future.

    # This should ideally go away when we go to infrastructure.yml
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

    # The following section goes away when we start using and updating
    # infrastructure_provisioning.yml.

    # This writes an overrides.yml with the key path. It does a coare
    # merge. It will override any other infrastructure_provisioning
    # entries
    setup_overrides(config, directory)

    setup_security_tf(config, directory)

    LOGGER.info("Local environment setup in %s", directory)

if __name__ == '__main__':
    main()
