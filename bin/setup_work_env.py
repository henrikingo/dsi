#!/usr/bin/env python2.7
# pylint: disable=relative-import,fixme

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

from common.log import setup_logging

LOGGER = logging.getLogger(__name__)

DEFAULT_CONFIG = {'cluster_type': 'single',
                  'aws_key_name': 'NoKeyName',
                  'aws_secret': "NoSecret",
                  'directory': '.',
                  'production': False,
                 }


def build_config(args=None):
    '''
    Build a config file, including the specified arguments
    '''
    # default values for config
    config = copy.copy(DEFAULT_CONFIG)

    # if we can read variables out of the ~/.aws/credentials file, do so
    read_aws_creds(config)

    # environment variables should supersede config file reading
    read_env_vars(config)

    # command-line options should supersede env vars and cred file
    parse_command_line(config, args)

    return config


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
        config['aws_key_name'] = config_parser.get('default', 'aws_access_key_id')
        config['aws_secret'] = config_parser.get('default', 'aws_secret_access_key')
    return config


def read_env_vars(config):
    '''
    Read AWS access key id and and secret access key from environment variables
    '''
    if 'AWS_ACCESS_KEY_ID' in os.environ:
        config['aws_key_name'] = os.environ.get('AWS_ACCESS_KEY_ID', 'NoKeyName')
    if 'AWS_SECRET_ACCESS_KEY' in os.environ:
        config['aws_secret'] = os.environ.get('AWS_SECRET_ACCESS_KEY', 'NoSecret')
    return config


def parse_command_line(config, args=None):
    #pylint: disable=line-too-long
    '''
    Parse the command line options for setting up a working directory

    >>> from collections import OrderedDict
    >>> OrderedDict(parse_command_line(copy.copy(DEFAULT_CONFIG), []))
    OrderedDict([('aws_secret', 'NoSecret'), ('cluster_type', 'single'), ('aws_key_name', 'NoKeyName'), ('directory', '.'), ('production', False)])

    >>> OrderedDict(parse_command_line(copy.copy(DEFAULT_CONFIG), ['-c', 'none']))
    OrderedDict([('aws_secret', 'NoSecret'), ('cluster_type', 'none'), ('aws_key_name', 'NoKeyName'), ('directory', '.'), ('production', False)])

    >>> OrderedDict(parse_command_line(copy.copy(DEFAULT_CONFIG), ['-c', 'none', '--mongo-download-url', "URL", "--aws-key-name", "key_name", "--ssh-keyfile-path", "keyfile", "--aws-secret-file", "newsecret.json"]))
    OrderedDict([('aws_secret', 'NoSecret'), ('ssh_keyfile_path', 'keyfile'), ('cluster_type', 'none'), ('aws_key_name', 'key_name'), ('aws_secret_file', 'newsecret.json'), ('production', False), ('directory', '.')])
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
                        '--aws-key-name',
                        help='AWS key name. If this flag is not used, the key name will default \
                        to the key name specified in the [default] section of ~/.aws/credentials, \
                        then to $AWS_ACCESS_KEY_ID if set, and to \'NoKeyName\' otherwise.')
    parser.add_argument('-s',
                        '--aws-secret-file',
                        help='File containing AWS secret. If this flag is not used, the secret \
                        will default to the secret specified in the [default] section of \
                        ~/.aws/credentials, then to $AWS_SECRET_ACCESS_KEY if set, and to \
                        \'NoSecret\' otherwise.')
    # To be replaced by infrastructure.yml selection option
    parser.add_argument('-c',
                        '--cluster-type',
                        help='Set the cluster type')
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
    parser.add_argument('-m',
                        '--mongo-download-url',
                        help='Ignored. (Backward compatibility.)')
    parser.add_argument('--mc',
                        help='The path of the mc executable. Defaults to $(which mc) if mc is \
                        in the PATH, and to $DSI_PATH/bin/mc if not.')
    parser.add_argument('--owner',
                        help='Owner tag for AWS resources')
    parser.add_argument('-p',
                        '--ssh-keyfile-path',
                        help="Path to AWS ssh key file (pem)")
    parser.add_argument('--ssh-key',
                        help="Key to use with SSH access")
    parser.add_argument('--production',
                        action='store_true',
                        help='Indicate the script is being called as part of a production run. '
                        'This suppresses certain messages appropriate for local runs')
    parser.add_argument('-v',
                        '--verbose',
                        action='store_true',
                        help='Enable verbose output')
    args = parser.parse_args(args)

    setup_logging(args.debug, args.log_file)  # pylint: disable=no-member

    if args.config:
        for conf in args.config:
            config.update(yaml.load(open(conf)))
    if args.cluster_type:
        config['cluster_type'] = args.cluster_type
    if args.aws_key_name:
        config['aws_key_name'] = args.aws_key_name
    if args.ssh_keyfile_path:
        config['ssh_keyfile_path'] = args.ssh_keyfile_path
    if args.ssh_key:
        config['ssh_key'] = args.ssh_key
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
    return config


def copy_config_files(dsipath, config, directory):
    '''
    Copy all related config files to the target directory

    Following files are copied:
        - infrastructure_provision.yml
    '''

    # Move the proper infrastructure_provisioning file to the target directory
    provisioning_file = os.path.join(dsipath,
                                     "configurations/infrastructure_provisioning",
                                     "infrastructure_provisioning." +
                                     config["cluster_type"] + ".yml")
    try:
        target = os.path.join(directory, "infrastructure_provisioning.yml")
        shutil.copyfile(provisioning_file, target)
        LOGGER.info("Copied " + provisioning_file + " to work directory %s.", target)
    except Exception as error:
        # We must have infrastructure provisioning file
        LOGGER.critical("Failed to copy infrastructure_provisioning.yml from %s.\nError: %s",
                        provisioning_file, str(error))
        raise

    # Copy other config files here
    return

def setup_overrides(config, directory):
    '''
    Generate the overrides.yml file
    '''

    overrides = {}
    override_path = os.path.join(directory, 'overrides.yml')
    tfvars = {}
    if 'ssh_keyfile_path' in config:
        tfvars['ssh_key_file'] = config['ssh_keyfile_path']
    if 'ssh_key' in config:
        tfvars['ssh_key'] = config['ssh_key']
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
        security.write('    access_key = "{0}"\n'.format(config['aws_key_name']))
        security.write('    secret_key = "{0}"\n'.format(config['aws_secret']))
        security.write('    region = "${var.region}"\n')
        security.write('}\n')
        security.write('variable "key_name" {\n')
        security.write('    default = "rui-aws-cap"\n')
        security.write('}\n')
        security.write('variable "key_file" {\n')
        security.write('    default = "missing"\n')
        security.write('}')


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

    # Create directory if it doesn't exist
    if not os.path.exists(directory):
        os.makedirs(directory)

    # TODO: Copy of persisted terraform information should be copied
    # into working directory here. This is future work to support tying
    # the terraform cluster to the evergreen runner.

    # Write out the dsienv.sh file. It saves the path to DSI repo
    with open(os.path.join(directory, 'dsienv.sh'), 'w') as dsienv:
        dsienv.write('export DSI_PATH={0}\n'.format(dsipath))
        dsienv.write('export PATH=$PATH:{0}/bin\n'.format(dsipath))
        dsienv.write('export MC={0}\n'.format(mission_control))

    # if we specified a secret file, use its contents as the aws secret
    if 'aws_secret_file' in config:
        # Read in the secret
        config['aws_secret'] = open(config['aws_secret_file']).read().rstrip()

    # Todo: This section should be replaced by code to select infrastructure.yml
    cluster_path = os.path.join(dsipath, 'clusters', config['cluster_type'])
    remote_scripts_path = os.path.join(dsipath, 'clusters', 'remote-scripts')
    # Copy over all files from cluster directory
    for filename in glob.glob(os.path.join(cluster_path, '*')):
        shutil.copy(filename, directory)

    # Copy over all files from the remote scripts directory Note that
    # this is copying above the workload directory for now. This is
    # suboptimal and should be changed in the future.

    # This should ideally go away when we go to infrastructure.yml
    remote_scripts_target = os.path.join(os.path.dirname(directory), 'remote-scripts')
    print ("remote_scripts_target is {}".format(remote_scripts_target))
    print ("remote_scripts_path is {}".format(remote_scripts_path))
    os.mkdir(remote_scripts_target)
    for filename in glob.glob(os.path.join(remote_scripts_path, '*')):
        shutil.copy(filename, remote_scripts_target)

    # copy modules
    modules_path = os.path.join(dsipath, 'clusters', 'modules')
    modules_target = os.path.join(os.path.dirname(directory), 'modules')
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

    print("Local environment setup in {0}".format(directory))

if __name__ == '__main__':
    main()
