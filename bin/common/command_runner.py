"""
Utilities for running commands on hosts
"""
from collections import MutableMapping
from functools import partial
import logging
import os

import common.host_factory
import common.host_utils
import common.utils
import common.mongodb_setup_helpers
from thread_runner import run_threads

LOG = logging.getLogger(__name__)


# https://jira.mongodb.org/browse/PERF-1311 will replace ssh_user and ssh_key_file with a
# NamedTuple, and remove the need for this pylint disable.
#pylint: disable=too-many-arguments
def make_host_runner(host_info, command, ssh_user, ssh_key_file, prefix,
                     mongodb_auth_settings=None):
    """
    For the host, make an appropriate RemoteHost or LocalHost Object and run the set of commands.

    :param namedtuple host_info: Public IP address or the string localhost, category and offset
    :param str ssh_user: The user id to use
    :param str ssh_key_file: The keyfile to use
    :param command: The command to execute. If str, run that command. If dict, type is one of
    upload_repo_files, upload_files, retrieve_files, exec, or exec_mongo_shell.
    :type command: str, dict
    :param str prefix: The id for the test related to the current command. If there
    is not a specific test related to the current command, the value of prefix should reflect the
    hook that the command belongs to, such as between_tests, post_task, and so on.
    """
    # Create the appropriate host type
    target_host = common.host_factory.make_host(host_info, ssh_user, ssh_key_file,
                                                mongodb_auth_settings)
    try:
        # If command is a string, pass it directly to run
        if isinstance(command, str):
            target_host.run(command)

        # If command is a dictionary, parse it
        elif isinstance(command, MutableMapping):
            _run_host_command_map(target_host, command, prefix)
    finally:
        target_host.close()


def _run_host_command(host_list, command, config, prefix):
    """
    For each host in the list, make a parallelized call to make_host_runner to make the appropriate
    host and run the set of commands.

    :param list host_list: List of ip addresses to connect to
    :param command: The command to execute. If str, run that command. If dict, type is one of
    upload_repo_files, upload_files, retrieve_files, exec, or exec_mongo_shell.
    :type command: str, dict
    :param ConfigDict config: The system configuration
    :param str prefix: The id for the test related to the current command. If there
    is not a specific test related to the current command, the value of prefix should reflect the
    hook that the command belongs to, such as between_tests, post_task, and so on.
    """
    if not host_list:
        return

    LOG.debug('Calling run command for %s with command %s', str(host_list), str(command))
    ssh_user = config['infrastructure_provisioning']['tfvars']['ssh_user']
    ssh_key_file = config['infrastructure_provisioning']['tfvars']['ssh_key_file']
    ssh_key_file = os.path.expanduser(ssh_key_file)

    mongodb_auth_settings = common.mongodb_setup_helpers.mongodb_auth_settings(config)
    thread_commands = []
    for host_info in host_list:
        thread_commands.append(
            partial(make_host_runner, host_info, command, ssh_user, ssh_key_file, prefix,
                    mongodb_auth_settings))

    run_threads(thread_commands, daemon=True)


def _run_host_command_map(target_host, command, prefix):
    """
    Run one command against a target host if the command is a mapping.

    :param Host target_host: The host to send the command to
    :param dict command: The command to execute
    :param str prefix: The id for the test related to the current command. If there
    is not a specific test related to the current command, the value of prefix should reflect the
    hook that the command belongs to, such as between_tests, post_task, and so on.

    :raises: UserWarning on error, HostException when there is a cmd or paramiko issue.
    **Note: retrieve_files does not directly raise exceptions on error**.
    """
    # pylint: disable=too-many-branches
    for key, value in command.iteritems():
        if key == "upload_repo_files":
            for paths in value:
                source = os.path.join(common.utils.get_dsi_path(), paths['source'])
                target = paths['target']
                LOG.debug('Uploading file %s to %s', source, target)
                target_host.upload_file(source, target)
        elif key == "upload_files":
            for paths in value:
                LOG.debug('Uploading file %s to %s', paths['source'], paths['target'])
                target_host.upload_file(paths['source'], paths['target'])
        elif key == "retrieve_files":
            for paths in value:
                source = paths['source']
                target = paths['target']
                if prefix:
                    target = os.path.join('reports', prefix, target_host.alias,
                                          os.path.normpath(target))
                else:
                    target = os.path.join('reports', target_host.alias, os.path.normpath(target))

                LOG.debug('Retrieving file %s from %s', source, target)
                target_host.retrieve_path(source, target)
        elif key == "exec":
            LOG.debug('Executing command %s', value)
            success = target_host.run(value.split(' '))
            common.host_utils.raise_if_not_success(success, value)
        elif key == "exec_mongo_shell":
            LOG.debug('Executing command %s in mongo shell', value)
            connection_string = value.get('connection_string', "")
            exit_status = target_host.exec_mongo_command(
                value['script'], connection_string=connection_string)
            common.host_utils.raise_if_not_ok(exit_status, value)
        elif key == "checkout_repos":
            for paths in value:
                source = paths['source']
                target = paths['target']
                branch = paths['branch'] if 'branch' in paths else None
                verbose = paths['verbose'] if 'verbose' in paths else False
                LOG.debug('Checking out git repository %s to %s', target, source)
                target_host.checkout_repos(source, target, str(branch), verbose=verbose)
        else:
            raise UserWarning("Invalid command type")


def run_host_command(target, command, config, prefix):
    """
    Sets up and runs a command for use on the appropriate hosts.

    :param str target: The target to run the command on
    :param dict command: The action to run
    :param ConfigDict config: The system configuration
    :param str prefix: The id for the test related to the current command. If there
    is not a specific test related to the current command, the value of prefix should reflect the
    hook that the command belongs to, such as between_tests, post_task, and so on.
    """

    assert isinstance(command, MutableMapping), "command isn't a dict"
    assert target.startswith('on_')

    keys = command.keys()
    target = target[3:]
    hosts = common.host_utils.extract_hosts(target, config)
    LOG.info("Running command(s) %s on %s", keys, target)
    _run_host_command(hosts, command, config, prefix)
    LOG.debug("Done running command(s) %s on %s", keys, target)


def run_host_commands(commands, config, prefix):
    """
    Plural version of run_host_command: run a list of commands.

    Example of commands:

    [
        { 'on_workload_client': { 'upload_files': [{ 'source': 'path', 'target': 'dest' }] } }
    ]

    :param list commands: List of dict actions to run
    :param ConfigDict config: The system configuration
    :param str prefix: The id for the test related to the current command. If there
    is not a specific test related to the current command, the value of prefix should reflect the
    hook that the command belongs to, such as between_tests, post_task, and so on.
    """
    for command in commands:
        # Item should be a map with one entry
        assert isinstance(command, MutableMapping), "command in list isn't a dict"
        assert len(command.keys()) == 1, "command has more than one entry"
        for target, target_command in command.iteritems():
            target = command.keys()[0]
            run_host_command(target, target_command, config, prefix)


def make_workload_runner_host(config):
    """
    Convenience function to make a host to connect to the workload runner node.

    :param ConfigDict config: The system configuration
    """
    ssh_key_file = config['infrastructure_provisioning']['tfvars']['ssh_key_file']
    ssh_key_file = os.path.expanduser(ssh_key_file)
    ssh_user = config['infrastructure_provisioning']['tfvars']['ssh_user']
    host_info = common.host_utils.extract_hosts('workload_client', config)[0]
    mongodb_auth_settings = common.mongodb_setup_helpers.mongodb_auth_settings(config)
    return common.host_factory.make_host(host_info, ssh_user, ssh_key_file, mongodb_auth_settings)
