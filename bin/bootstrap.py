#!/usr/bin/env python2.7
"""
Setup an work environment. Copy over the appropriate files.
"""

from __future__ import print_function
import sys
import argparse
import os
import os.path
import shutil
import subprocess
import structlog
import yaml

from common.config import ConfigDict
from common.log import setup_logging
import common.utils

LOGGER = structlog.get_logger(__name__)


def parse_command_line(config, args=None):
    """
    Parse the command line options for setting up a working directory

    :param dict config: The bootstrap.py config, populated from cli options. (NOT ConfigDict.)
    :param list args: Command line arguments to pass to argparse.
    """

    parser = argparse.ArgumentParser(description='Setup DSI working environment. For instructions \
                    on setting up dsi locally, see \
                    https://drive.google.com/open?id=14QXOmo-ia8w72pW5zqQ2fCWfXEwiVQ8_1EoMCkB4baY')

    parser.add_argument(
        '-b',
        '--bootstrap-file',
        help='Specify the bootstrap file. If not specified, will look for '
        'bootstrap.yml in the current directory. ')
    parser.add_argument('-d', '--debug', action='store_true', help='enable debug output')
    parser.add_argument(
        '-D', '--directory', default='.', help="Directory to setup. Defaults to current directory")
    parser.add_argument('--log-file', help='path to log file')

    # These options are ignored but allowed for backward compatibility
    parser.add_argument('--production', action='store_true', default=False, help='(Ignored)')
    parser.add_argument('-v', '--verbose', action='store_true', help='(Ignored, use -d instead.)')
    args = parser.parse_args(args)

    setup_logging(args.debug, args.log_file)  # pylint: disable=no-member

    if args.bootstrap_file:
        config['bootstrap_file'] = args.bootstrap_file
    if args.directory:
        config['directory'] = args.directory
    return config


def copy_config_files(dsipath, config, directory):
    """
    Copy all related config files to the target directory

    :param str dsipath: Path to DSI repo.
    :param dict config: The bootstrap.py internal config.
    :param str directory: The work directory.
    """
    # Pairs of ConfigDict module, and bootstrap.yml input.
    # This is all the variable info needed to build the from and to file paths down below.
    configs_to_copy = {
        "infrastructure_provisioning": config.get("infrastructure_provisioning", ""),
        "mongodb_setup": config.get("mongodb_setup", ""),
        "test_control": config.get("test_control", ""),
        "workload_setup": config.get("workload_setup", ""),
        "analysis": config.get("analysis", "")
    }

    for config_module, bootstrap_variable in configs_to_copy.iteritems():
        # Example: ./mongodb_setup.yml
        target_file = os.path.join(directory, config_module + ".yml")
        # Example: ../dsi/configurations/mongodb_setup/mongodb_setup.standalone.wiredTiger.yml
        source_file = os.path.join(dsipath, "configurations", config_module,
                                   config_module + "." + bootstrap_variable + ".yml")

        _warn_if_overwriting(target_file)
        #pylint: disable=broad-except
        try:
            shutil.copyfile(source_file, target_file)
            LOGGER.debug(
                "Copied file to work directory", source_file=source_file, target_file=target_file)
        except Exception as error:
            # If a source file doesn't exist, it's probably because a wrong or no option was
            # provided in bootstrap.yml. When running manually, this is not fatal. For example,
            # user may want to manually copy some files from somewhere else
            error_str = "Failed to copy {} from {}.\nError: {}".format(
                target_file, source_file, str(error))
            if config["production"]:
                LOGGER.critical(error_str)
                raise
            else:
                LOGGER.warn(error_str)
    return


def setup_overrides(config_dict, directory):
    """
    Generate the overrides.yml file

    :param ConfigDict config_dict: The ConfigDict object. Note, must be a real ConfigDict instance,
                                   passing a dict will fail.
    :param str directory: The work directory.
    """
    # Use the raw dict to prevent ${variable.references} from being prematurely evaluated.
    overrides = config_dict.raw['bootstrap'].get('overrides', {})
    override_path = os.path.join(directory, 'overrides.yml')

    # A bit odd place, but this used to be here when code was different, so leaving here for now
    try:
        if overrides['infrastructure_provisioning']['tfvars']['tags']['owner'] == 'your.username':
            message = "owner is set to your.username. Please update this setting in your " \
                    "bootstrap.yml file, and review the other settings in that file."
            LOGGER.critical(message)
            assert False, message
    except KeyError:
        pass
    except TypeError:
        pass

    if overrides:
        _warn_if_overwriting(override_path)
        with open(override_path, 'w') as override_file:
            override_file.write(yaml.dump(overrides, default_flow_style=False))


def find_terraform(config, directory):
    """
    Returns the location of the terraform binary to use.

    :param dict config: The bootstrap.py internal config.
    :param str directory: The work directory.
    """
    try:
        system_tf = subprocess.check_output(['which', 'terraform']).strip()
    except subprocess.CalledProcessError:
        system_tf = None

    if 'terraform' in config:
        terraform = os.path.abspath(os.path.expanduser(config['terraform']))
        LOGGER.debug(
            'Using terraform binary specified by bootstrap.terraform',
            terraform=config['terraform'])
    elif system_tf is not None:
        terraform = os.path.abspath(system_tf)
        LOGGER.debug('Using terraform binary specified by $(which terraform)', terraform=terraform)
    else:
        terraform = os.path.join(directory, 'terraform')
        LOGGER.debug('Using terraform binary in default location', terraform=terraform)

    LOGGER.info('Path to terraform binary', terraform=terraform)
    return terraform


def validate_terraform(config):
    """
    Asserts that terraform is the correct version.

    :param dict config: The bootstrap.py internal config.
    """
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
            LOGGER.critical('You are using %s, but DSI requires %s.', version,
                            config['terraform_version_check'])
            LOGGER.critical("See documentation for installing terraform: http://bit.ly/2ufjQ0R")
            assert False


def write_dsienv(directory, terraform):
    """
    Writes out the dsienv.sh file.

    :param str directory: The work directory.
    :param str terraform: Path to terraform.

    """
    with open(os.path.join(directory, 'dsienv.sh'), 'w') as dsienv:
        dsienv.write('export PATH={0}:$PATH\n'.format(common.utils.get_dsi_bin_dir()))
        dsienv.write('export TERRAFORM={0}'.format(terraform))


def load_bootstrap(config, directory):
    """
    Move specified bootstrap.yml file to correct location for read_runtime_values
    """
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
        bootstrap_path = os.path.abspath(
            os.path.expanduser(os.path.join(os.getcwd(), 'bootstrap.yml')))
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


def _warn_if_overwriting(destination):
    """
    Warn if destination exists.

    :param str destination: A path to a config file.
    """
    if os.path.exists(destination):
        LOGGER.warn("Overwriting existing file.", destination=destination)


def main():
    """
    Main function for setting up working directory
    """

    config = {}
    parse_command_line(config)
    directory = os.path.abspath(os.path.expanduser(config['directory']))
    LOGGER.info('Creating work directory', directory=directory)

    if os.path.exists(os.path.join(directory, 'dsienv.sh')):
        print("It looks like you have already setup "
              "{0} for dsi. dsienv.sh exists. Stopping".format(directory))
        sys.exit(1)

    # Copies bootstrap.yml if necessary and then reads values into config
    config_dict = load_bootstrap(config, directory)

    # Checks for aws credentials, fails if cannot find them
    common.utils.read_aws_credentials(config_dict)

    config['terraform'] = find_terraform(config, directory)
    validate_terraform(config)

    write_dsienv(directory, config['terraform'])

    # copy necessary config files to the current directory
    copy_config_files(common.utils.get_dsi_path(), config, directory)

    # This writes an overrides.yml with the ssh_key_file, ssh_key_name and owner, if given in
    # bootstrap.yml, and with expire-on-delta if running DSI locally.
    setup_overrides(config_dict, directory)

    LOGGER.info("Local environment setup", directory=directory)


if __name__ == '__main__':
    main()
