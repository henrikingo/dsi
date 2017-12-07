#!/usr/bin/env python2.7
""" Test runner in DSI Framework """

from __future__ import print_function
from collections import MutableMapping
import argparse
import copy
import logging
import os
import shutil
import subprocess
import sys
import inspect
from enum import Enum

from common.config import ConfigDict
from common.host import extract_hosts, run_host_command
from common.log import setup_logging
import config_test_control
import mongodb_setup

LOG = logging.getLogger(__name__)

EXCEPTION_BEHAVIOR = Enum('Exception Behavior', 'CONTINUE RERAISE EXIT')


def setup_ssh_agent(config):
    ''' Setup the ssh-agent, and update our environment for it.

    :param ConfigDict config: The system configuration
    '''

    ssh_agent_info = subprocess.check_output(['ssh-agent', '-s'])
    # This expansion updates our environment by parsing the info from the previous line
    # It splits the data into lines, and then for any line of the form
    # "key=value", adds {key: value} to the environment
    os.environ.update(dict([line.split('=') for line in ssh_agent_info.split(';') if '=' in line]))
    ssh_key_file = config['infrastructure_provisioning']['tfvars']['ssh_key_file']
    ssh_key_file = os.path.expanduser(ssh_key_file)
    subprocess.check_call(['ssh-add', ssh_key_file])


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


def run_pre_post_commands(command_key,
                          command_dicts,
                          config,
                          exception_behavior,
                          current_test_id=None):
    ''' Runs all commands with the specified command key. If exit on exception is
    true, exit from the script. Otherwise, print the trace and continue.

    :param string command_key: The key to use to find a command list to execute in each of the
    command_dicts.
    :param list(ConfigDict) command_dicts: List of ConfigDict objects that may have the specified
    command_section.
    :param dict(ConfigDict) config: The system configuration.
    :param EXCEPTION_BEHAVIOR exception_behavior: Indicates the proper action to take upon catching
    an exception.
    :param string current_test_id: Indicates the id for the test related to the current set of
    commands. If there is not a specific test related to the current set of commands, the value of
    current_test_id will be None.
    '''
    for command_dict in command_dicts:
        if command_key in command_dict:
            try:
                dispatch_commands(command_key, command_dict[command_key], config, current_test_id)
            except Exception as exception:  #pylint: disable=broad-except
                print_trace(inspect.trace(), exception)
                if exception_behavior == EXCEPTION_BEHAVIOR.RERAISE:
                    raise exception
                elif exception_behavior == EXCEPTION_BEHAVIOR.EXIT:
                    LOG.error("Exiting with status code: 1")
                    sys.exit(1)
                elif exception_behavior == EXCEPTION_BEHAVIOR.CONTINUE:
                    pass
                else:
                    LOG.error("Invalid exception_behavior entry")


def dispatch_commands(command_key, command_list, config, currrent_test_id=None):
    ''' Routes commands to the appropriate command runner. The command runner will run the command.

    :param string command_key: The key to use to find a command list to execute in each of the
    command_dicts. Used for error handling only.
    :param list(dict) command_list: A list of commands to run
    :param dict(ConfigDict) config: The system configuration.
    :param string current_test_id: Indicates the id for the test related to the current set of
    commands. If there is not a specific test related to the current set of commands, the value of
    current_test_id will be None.
    '''
    for item in command_list:
        # Item should be a map with one entry
        assert isinstance(item, MutableMapping), 'item in list isn\'t a dict'
        assert len(item.keys()) == 1, 'item has more than one entry'
        for target, command in item.iteritems():
            if target.startswith('on_'):
                run_host_command(target, command, config, currrent_test_id)
            elif target == "restart_mongodb":
                mongo_controller = mongodb_setup.MongodbSetup(config)
                clean_db_dir = command['clean_db_dir']
                clean_logs = command['clean_logs']
                if not mongo_controller.restart(clean_db_dir, clean_logs):
                    raise Exception("Error restarting mongodb")
            else:
                raise KeyError("Unknown {} target {}".format(command_key, target))


def print_trace(trace, exception):
    """ print exception information for run_pre_post_commands. Information corresponds
    to YAML file tasks

    :param list((frame_object, string, int,
                 string, list(string), int)) trace: returned by inspect.trace()
    Refer to python docs:
    https://docs.python.org/2/library/inspect.html#inspect.trace
    https://docs.python.org/2/library/inspect.html#the-interpreter-stack
    Each element in the list is a "tuple of six items: the frame object, the filename, the line
    number of the current line, the function name, a list of lines of context from the source code,
    and the index of the current line within that list"

    :param Exception() exception: this is the exception raised by one of tasks

    *NOTE* This function is dependent on the stack frames of the function calls made within
    run_pre_post_commands along with the variable names in run_pre_post_commands,
    run_host_command, dispatch_commands, and _run_host_command_map. Changes in the variable names
    or the flow of function calls could cause print_trace to log wrong/unhelpful info.
    """
    top_function = trace[0][3]
    bottom_function = trace[-1][3]
    bottom_function_file = trace[-1][1]
    bottom_function_line = str(trace[-1][2])
    # This conditional does not cause any errors due to lazy evaluation
    if len(trace) > 1 and 'target' in trace[1][0].f_locals:
        executed_task = trace[1][0].f_locals['target']
    else:
        executed_task = ""
    executed_command = {}
    for frame in trace:
        if frame[3] == "run_host_command" and executed_command == {}:
            executed_command = frame[0].f_locals['command']
        if frame[3] == "_run_host_command_map":
            executed_command[frame[0].f_locals['key']] = frame[0].f_locals['value']
    error_msg = "Exception originated in: " + bottom_function_file
    error_msg = error_msg + ":" + bottom_function + ":" + bottom_function_line
    error_msg = error_msg + "\n" + "Exception msg: " + str(exception)
    error_msg = error_msg + "\n" + top_function + ":"
    if executed_task != '':
        error_msg = error_msg + "\n    in task: " + executed_task
    if executed_command != {}:
        error_msg = error_msg + "\n" + "        in command: " + str(executed_command)
    LOG.error(error_msg)


def copy_timeseries(config):
    """ copy the files required for timeseries analysis from
    their legacy mission-control locations to the new locations used by host.py.

    :param dict(ConfigDict) config: The system configuration

    """
    hosts = extract_hosts('all_servers', config)
    for root, _, files in os.walk('./reports'):
        for name in files:
            # The following generator find the first host with an ip that matches
            # the filename. The (.. for in if in ) generator will return 0 or more
            # matches.
            #
            # In the non matching case, next would throw StopIteration . The
            # None final param ensures that something 'Falsey' is returned instead.
            host = next((host for host in hosts if name.endswith(host.ip_or_name)), None)
            if host:
                source = os.path.join(root, name)
                alias = "{category}.{offset}".format(category=host.category, offset=host.offset)

                destination = "{}-{}".format(
                    os.path.basename(source).split('--')[0], os.path.basename(root))
                destination = os.path.join('reports', alias, destination)
                shutil.copyfile(source, destination)


def main(argv):
    ''' Main function. Parse command line options, and run tests '''
    parser = argparse.ArgumentParser(description='DSI Test runner')

    # These were left here for backward compatibility.
    parser.add_argument('foo', help='Ignored', nargs='?')
    parser.add_argument('bar', help='Ignored', nargs='?')
    parser.add_argument('czar', help='Ignored', nargs='?')

    parser.add_argument('-d', '--debug', action='store_true', help='enable debug output')
    parser.add_argument('--log-file', help='path to log file')
    args = parser.parse_args(argv)
    setup_logging(args.debug, args.log_file)
    config = ConfigDict('test_control')
    config.load()

    test_control_config = config['test_control']
    mongodb_setup_config = config['mongodb_setup']

    dsi_bin_path = os.path.join(os.path.dirname(os.path.abspath(__file__)))

    mission_control = os.path.join(dsi_bin_path, 'mc')
    if 'MC' in os.environ:
        mission_control = os.environ['MC']

    setup_ssh_agent(config)
    cleanup_reports()

    # TODO: Change the order of test_control and mongodb_setup_config
    # https://jira.mongodb.org/browse/PERF-1160
    # Execute pre task steps
    run_pre_post_commands('pre_task', [test_control_config, mongodb_setup_config], config,
                          EXCEPTION_BEHAVIOR.EXIT)

    try:
        # initialSync is still executed through the old bash script
        if config['test_control']['task_name'] == 'initialSync':
            subprocess.check_call([
                os.path.join(dsi_bin_path, 'run-initialSync.sh'),
                config['mongodb_setup']['mongod_config_file']['storage']['engine'], 'initialSync',
                config['infrastructure_provisioning']['tfvars']['cluster_name']
            ])
        else:
            # Everything should eventually come through this path
            # Call mission control
            # Pass in MC_MONITOR_INTERVAL=config.test_control.mc_monitor_interval to environment
            env = copy.deepcopy(os.environ)
            env['MC_MONITOR_INTERVAL'] = str(config['test_control']['mc']['monitor_interval'])
            env['MC_PER_THREAD_STATS'] = str(config['test_control']['mc']['per_thread_stats'])
            LOG.debug('env for mc call is %s', str(env))

            if os.path.exists('perf.json'):
                os.remove('perf.json')
                LOG.warning("Found old perf.json file. Overwriting.")

            try:
                for index, test in enumerate(test_control_config['run']):
                    try:
                        # Generate the mc.json file for this test only. Save it to unique name
                        config_test_control.generate_mc_json(test_index=index)
                        mc_config_file = 'mc_' + test['id'] + '.json'

                        # Only run between_tests after the first test.
                        if index > 0:
                            run_pre_post_commands('between_tests',
                                                  [mongodb_setup_config, test_control_config],
                                                  config, EXCEPTION_BEHAVIOR.RERAISE)
                        run_pre_post_commands('pre_test',
                                              [mongodb_setup_config, test_control_config, test],
                                              config, EXCEPTION_BEHAVIOR.RERAISE, test['id'])

                        subprocess.check_call(
                            [
                                mission_control, '-config', mc_config_file, '-run', test['id'],
                                '-o', 'perf.json'
                            ],
                            env=env)
                    finally:
                        run_pre_post_commands('post_test',
                                              [test, test_control_config, mongodb_setup_config],
                                              config, EXCEPTION_BEHAVIOR.CONTINUE, test['id'])

            finally:
                run_pre_post_commands('post_task', [test_control_config, mongodb_setup_config],
                                      config, EXCEPTION_BEHAVIOR.CONTINUE)

    finally:
        # Set perf.json to 555
        # Todo: replace with os.chmod call or remove in general
        # Previously this was set to 777. I can't come up with a good reason.
        subprocess.check_call(['chmod', '555', 'perf.json'])

        copy_perf_output()


if __name__ == '__main__':
    main(sys.argv[1:])
