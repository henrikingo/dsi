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
import sys
import argparse
import glob
import logging
import os
import os.path
import shutil
import subprocess
import yaml

from common.log import setup_logging

LOGGER = logging.getLogger(__name__)

def parse_command_line(args=None):
    '''
    Parse the command line options for setting up a working directory

    >>> from collections import OrderedDict
    >>> OrderedDict(parse_command_line([]))
    OrderedDict([('aws_secret', 'NoSecret'), ('production', False), ('ssh_keyfile_path',\
 'InvalidPath'), ('mongo_download_url',\
 'https://fastdl.mongodb.org/linux/mongodb-linux-x86_64-amazon-3.2.3.tgz'),\
 ('directory', '.'), ('cluster_type', 'single'), ('region', None), ('aws_key_name',\
 'InvalidKeyName')])

    >>> OrderedDict(parse_command_line(['-c', 'none']))
    OrderedDict([('aws_secret', 'NoSecret'), ('production', False), ('ssh_keyfile_path',\
 'InvalidPath'), ('mongo_download_url',\
 'https://fastdl.mongodb.org/linux/mongodb-linux-x86_64-amazon-3.2.3.tgz'),\
 ('directory', '.'), ('cluster_type', 'none'), ('region', None),\
 ('aws_key_name', 'InvalidKeyName')])

    >>> OrderedDict(parse_command_line(['-c', 'none', '--mongo-download-url', "URL",\
 "--aws-key-name", "key_name", "--ssh-keyfile-path", "keyfile", "--region", "AWS Region",\
 "--aws-secret-file", "newsecret.json"]))
    OrderedDict([('aws_secret', 'NoSecret'), ('production', False), ('ssh_keyfile_path',\
 'keyfile'), ('mongo_download_url', 'URL'), ('directory', '.'), ('cluster_type', 'none'),\
 ('region', 'AWS Region'), ('aws_key_name', 'key_name'), ('aws_secret_file', 'newsecret.json')])

    '''

    parser = argparse.ArgumentParser(description='Setup DSI working environment')

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
                        help='AWS key name')
    parser.add_argument('-s',
                        '--aws-secret-file',
                        help='File containing AWS secret')
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
                        help='URL to download mongodb binaries from')
    parser.add_argument('-r',
                        '--region',
                        help='AWS Region')
    parser.add_argument('-p',
                        '--ssh-keyfile-path',
                        help="Path to AWS ssh key file (pem)")
    parser.add_argument('--production',
                        action='store_true',
                        help='Indicate the script is being called as part of a production run. '
                        'This suppresses certain messages appropriate for local runs')
    parser.add_argument('-v',
                        '--verbose',
                        action='store_true',
                        help='Enable verbose output')
    args = parser.parse_args(args)

    # To be replaced by system map
    config = {'cluster_type': 'single',
              'mongo_download_url':
              "https://fastdl.mongodb.org/linux/mongodb-linux-x86_64-amazon-3.2.3.tgz",
              'aws_key_name': "InvalidKeyName",
              'ssh_keyfile_path': "InvalidPath",
              'aws_secret': "NoSecret",
              'region': None,
              'directory': '.',
              'production': False,
             }

    setup_logging(args.debug, args.log_file)  # pylint: disable=no-member

    if args.config:
        for conf in args.config:
            config.update(yaml.load(open(conf)))
    if args.cluster_type:
        config['cluster_type'] = args.cluster_type
    if args.mongo_download_url:
        config['mongo_download_url'] = args.mongo_download_url
    if args.aws_key_name:
        config['aws_key_name'] = args.aws_key_name
    if args.ssh_keyfile_path:
        config['ssh_keyfile_path'] = args.ssh_keyfile_path
    if args.directory:
        config['directory'] = args.directory
    if args.region:
        config['region'] = args.region
    if args.aws_secret_file:
        config['aws_secret_file'] = args.aws_secret_file
    if args.production:
        config['production'] = True

    return config

def main():
    ''' Main function for setting up working directory
    '''

    config = parse_command_line()
    directory = os.path.abspath(os.path.expanduser(config['directory']))

    if os.path.exists(os.path.join(directory, 'dsienv.sh')):
        print ("It looks like you have already setup "
               "{0} for dsi. dsienv.sh exists. Stopping".format(directory))
        sys.exit(1)

    # Compute DSI Path based on directory location of this script. Go up one level
    dsipath = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    LOGGER.info('dsipath is %s', dsipath)

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

    if 'aws_secret_file' in config:
        # Read in the secret
        config['aws_secret'] = open(config['aws_secret_file']).read().rstrip()

    #Todo: This section should be replaced by code to select infrastructure.yml
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

    # Set the region file
    if config['region']:
        LOGGER.info("Setting up region file with region %s", config['region'])
        with open(os.path.join(directory, "aws-region"), 'w') as region:
            region.write(config['region'] + '\n')

    # Touch ips.sh so settings.sh doesn't complain
    open((os.path.join(directory, 'ips.sh')), 'w').close()

    # update settings.sh with proper key file
    with open(os.path.join(directory, 'setting.sh'), 'a') as settings:
        settings.write('export PEMFILE={0}\n'.format(config['ssh_keyfile_path']))

    # In the long term this code should change to update the config
    # file infrastructure.yml, or to generate it.

    # make_terraform_env.sh replaces values in various tf and tfvar
    # files for the cluster. Ideally all these changes should be in
    # the terraform.tfvar file, an that file should be json
    # formatted. The code is moving in that direction. When all
    # changes are isolated to the tfvars, and the tfvar file is in
    # json, we can replace the call to make_terraform_env.sh with
    # reading the json file, updating the appropriate values, and
    # re-writing the file.
    LOGGER.info("Calling make_terraform_env with keyname=%s, secret=XXXX, and url=%s",
                config['aws_key_name'], config['mongo_download_url'])
    subprocess.call([os.path.join(dsipath, 'bin', 'make_terraform_env.sh'),
                     config['aws_key_name'],
                     config['aws_secret'],
                     config['mongo_download_url']], cwd=directory)

    # The following section goes away when we start using and updating
    # infrastructure_provisioning.yml.

    # This writes an overrides.yml with the key path. It does a coare
    # merge. It will override any other infrastructure_provisioning
    # entries
    overrides = {}
    override_path = os.path.join(directory, 'overrides.yml')
    if os.path.exists(override_path):
        with open(override_path) as override_file:
            overrides = yaml.load(override_file)
    overrides.update({'infrastructure_provisioning':
                      {'tfvars': {'ssh_key_file': config['ssh_keyfile_path']}}})
    with open(override_path, 'w') as override_file:
        override_file.write(yaml.dump(overrides, default_flow_style=False))

    # This should be replaced by json manipulation. However the
    # special characters in the json files for templating keep python
    # from being able to parse them
    LOGGER.info("Calling update_pem_file_path.sh with %s", config['ssh_keyfile_path'])
    subprocess.call([os.path.join(dsipath, 'bin', 'update_pem_file_path.sh'),
                     config['ssh_keyfile_path']], cwd=directory)

    # Long term everything that needs to be specified in the config
    # files is handled above, and the following warning can be
    # removed.

    # Prompt the user to edit it.
    if not config['production']:
        print("Local environment setup in {0}".format(directory))
        print("Please review/edit security.tf and terraform.tfvars for your setup,"
              " before continuing deployment")
        print("You may need to update the owner, user, and key_name fields in those files")

if __name__ == '__main__':
    main()
