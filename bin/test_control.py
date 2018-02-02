#!/usr/bin/env python2.7
""" Test runner in DSI Framework """

from __future__ import print_function

import argparse
from collections import MutableMapping

import datetime
from enum import Enum
import inspect
import logging
import os
import shutil
import subprocess
import sys
import threading
import time
import yaml

from dateutil import tz
from nose.tools import nottest

from common.utils import mkdir_p
from common.config import ConfigDict
from common.host import extract_hosts, make_host, run_host_command, make_workload_runner_host
from common.host import setup_ssh_agent
from common.host import INFO_ADAPTER
from common.jstests import run_validate
import common.log
from common.workload_output_parser import parse_test_results, validate_config
import mongodb_setup
from workload_setup import WorkloadSetupRunner

LOG = logging.getLogger(__name__)

EXCEPTION_BEHAVIOR = Enum('Exception Behavior', 'CONTINUE RERAISE EXIT')


def prepare_reports_dir(reports_dir='reports'):
    """ Prepare the reports directory to receive test data (logs, diagnostics etc).
    Unlink the current reports directory and remove any tar ball. Then create a timestamped
    directory and sym link to reports_dir
    :param str reports_dir: the reports directory name. Defaults to reports
    :raises OSError: when reports_dir exists and it is a directory.
    """

    if os.path.exists(reports_dir):
        os.remove(reports_dir)

    if os.path.exists('../reports.tgz'):
        os.remove('../reports.tgz')

    real_reports_dir = "{}-{}".format(reports_dir, datetime.datetime.now(tz.tzlocal()).isoformat())
    mkdir_p(real_reports_dir)
    os.symlink(real_reports_dir, reports_dir)


def legacy_copy_perf_output():
    ''' Put perf.json in the legacy place for backward compatibility'''
    if os.path.exists('../perf.json'):
        os.remove('../perf.json')
    shutil.copyfile('perf.json', '../perf.json')

    # Read perf.json into the log file
    with open('../perf.json') as perf_file:
        for line in perf_file:
            LOG.info(line.rstrip())


def generate_config_file(test, local_dir, client_host):
    """
    Generate configuration files from the test run, save them in the report directory, and upload
    them to the client host

    :param ConfigDict test: The configuration for the test
    :param str local_dir: The local directory where the configuration file should be stored
    :param Host client_host: The client host to which the configuration file will be uploaded
    """
    try:
        filepath = os.path.join(local_dir, test['config_filename'])
        workload_config = test['workload_config']
        with open(filepath, 'w') as workloads_file:
            if isinstance(workload_config, ConfigDict):
                # Can't assign into config dict. Need an actual dictionary
                workload_config_dict = workload_config.as_dict()
                if 'scale_factor' in workload_config_dict and isinstance(
                        workload_config_dict['scale_factor'], str):
                    #pylint: disable=eval-used
                    workload_config_dict['scale_factor'] = eval(
                        workload_config_dict['scale_factor'])
                workloads_file.write(yaml.dump(workload_config_dict))
            elif isinstance(workload_config, str):
                workloads_file.write(workload_config)
        client_host.upload_file(filepath, test['config_filename'])
    except KeyError:
        LOG.warn("No workload config in test control")


def run_pre_post_commands(command_key,
                          command_dicts,
                          config,
                          exception_behavior,
                          current_test_id=None):
    ''' Runs all commands with the specified command key. If exit on exception is
    true, exit from the script. Otherwise, print the trace and continue.

    :param str command_key: The key to use to find a command list to execute in each of the
    command_dicts.
    :param list(ConfigDict) command_dicts: List of ConfigDict objects that may have the specified
    command_section.
    :param dict(ConfigDict) config: The system configuration.
    :param EXCEPTION_BEHAVIOR exception_behavior: Indicates the proper action to take upon catching
    an exception.
    :param str current_test_id: Indicates the id for the test related to the current set of
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


def dispatch_commands(command_key, command_list, config, current_test_id=None):
    ''' Routes commands to the appropriate command runner. The command runner will run the command.

    :param str command_key: The key to use to find a command list to execute in each of the
    command_dicts. Used for error handling only.
    :param list(dict) command_list: A list of commands to run
    :param dict(ConfigDict) config: The system configuration.
    :param str current_test_id: Indicates the id for the test related to the current set of
    commands. If there is not a specific test related to the current set of commands, the value of
    current_test_id will be None.
    '''
    # Most notably, the prefix is used for directory name under reports/.
    # It is either the test id (fio, ycsb_load...) or the command itself (post_task).
    prefix = current_test_id if current_test_id else command_key

    for item in command_list:
        # Item should be a map with one entry
        assert isinstance(item, MutableMapping), 'item in list isn\'t a dict'
        assert len(item.keys()) == 1, 'item has more than one entry'
        for target, command in item.iteritems():
            if target.startswith('on_'):
                run_host_command(target, command, config, prefix)
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


class BackgroundCommand(object):
    """ create a command that can be run in the background"""

    def __init__(self, host, command, filename):
        """Note: This class only works with RemoteHost today, not the parent Host class. See
        https://jira.mongodb.org/browse/PERF-1215

        :param RemoteHost host: the remote host to run the command on. This host will be closed
        at the end of it's life span so must not be used for anything else.
        :param str or list command: the shell command to execute.
        :param str filename: the location to write the logs to. Any missing directories will be
        created. The file will be closed on completion of the command or when close is called.

        """
        self.host = host
        self.command = command
        self.filename = filename

    def run(self):
        """ run the command. no checking is done with this instance. If it is called multiple times
        it will attempt to run multiple times. As host is closed, only the first call will succeed.

        The file is opened with 'wb+' so previous contents will be lost. """
        # 0 => no buffering
        mkdir_p(os.path.dirname(self.filename))
        with open(self.filename, 'wb+', 0) as out:
            self.host.exec_command(self.command, stdout=out, stderr=out, get_pty=True)

    def stop(self):
        """ stop the process, by closing the connnection to the host. This
         works because of the pty=True in the exec_comand call."""
        self.host.close()


# pylint: disable=too-many-locals
def start_background_tasks(config, command_dict, test_id, reports_dir='./reports'):
    """
    create any directories that are required and then evaluate the list of background task.
    :param dict(configDic) config: the overall configuration.
    :param dict command_dict: the command dict.
    :param str test: the name of the current test.
    :param str reports_dir: the report directory.
    """
    background_tasks = []
    if 'background_tasks' not in command_dict:
        LOG.info('%s BackgroundTask:map {}', test_id)
    else:
        background_tasks_spec = command_dict['background_tasks']
        LOG.info('%s BackgroundTask:map %s', test_id, background_tasks_spec)
        task_name = config['test_control']['task_name']
        ssh_key_file = config['infrastructure_provisioning']['tfvars']['ssh_key_file']
        ssh_key_file = os.path.expanduser(ssh_key_file)
        ssh_user = config['infrastructure_provisioning']['tfvars']['ssh_user']

        for name, command in background_tasks_spec.iteritems():
            # only a single workload_client is currently possible
            host_info = extract_hosts('workload_client', config)[0]
            remote_host = make_host(host_info, ssh_user, ssh_key_file)
            basename = "{}.log--{}@{}".format(name, remote_host.user, remote_host.alias)
            filename = os.path.join(reports_dir, task_name, test_id, basename)
            background = BackgroundCommand(remote_host, command, filename)
            thread = threading.Thread(target=background.run)
            thread.daemon = True
            thread.start()

            background_tasks.append(background)

    return background_tasks


def stop_background_tasks(background_tasks):
    """ stop all the background tasks """
    if background_tasks:
        LOG.info('stopping %s BackgroundTask%s', len(background_tasks), ""
                 if len(background_tasks) == 1 else "")

        for background_task in background_tasks:
            background_task.stop()


@nottest
def run_test(test, config, reports_dir='reports'):
    """
    Run one test. This creates a Host object, runs the command, and saves the output to a file.

    :param test ConfigDict: The ConfigDict object for the test to run
    :param config ConfigDict: The top level ConfigDict
    :param str reports_dir: The report directory
    """
    directory = os.path.join(reports_dir, test['id'])
    filename = os.path.join(directory, 'test_output.log')
    mkdir_p(directory)
    client_host = make_workload_runner_host(config)

    no_output_timeout_ms = config['test_control']['timeouts']['no_output_ms']

    # Generate and upload the test's configuration file if there is one
    generate_config_file(test, directory, client_host)

    with open(filename, 'wb+', 0) as out:
        tee_out = common.log.TeeStream(INFO_ADAPTER, out)
        error = client_host.exec_command(
            test['cmd'], stdout=tee_out, stderr=tee_out, no_output_timeout_ms=no_output_timeout_ms)
        if error:
            # To match previous behavior, we are raising a CalledProcessError
            # TODO: we should mark the test as failed in perf.json
            raise subprocess.CalledProcessError(error, test['cmd'])

    # Automatically retrieve output files, if specified, and put them into the reports directory
    if 'output_files' in test:
        for output_file in test['output_files']:
            client_host.retrieve_path(output_file,
                                      os.path.join(directory, os.path.basename(output_file)))

    client_host.close()


@nottest
def run_tests(config):
    """Main logic to run tests"""
    test_control_config = config['test_control']
    mongodb_setup_config = config['mongodb_setup']

    setup_ssh_agent(config)
    prepare_reports_dir()

    validate_config(config)
    run_pre_post_commands('pre_task', [mongodb_setup_config, test_control_config], config,
                          EXCEPTION_BEHAVIOR.EXIT)

    if 'test_delay_seconds' in test_control_config:
        test_delay_seconds = test_control_config['test_delay_seconds']
    else:
        test_delay_seconds = 0

    # pylint: disable=too-many-nested-blocks
    try:
        if os.path.exists('perf.json'):
            os.remove('perf.json')
            LOG.warning("Found old perf.json file. Overwriting.")

        for index, test in enumerate(test_control_config['run']):
            background_tasks = []
            LOG.info('running test %s', test)
            try:
                # Only run between_tests after the first test.
                if index > 0:
                    run_pre_post_commands('between_tests',
                                          [mongodb_setup_config, test_control_config], config,
                                          EXCEPTION_BEHAVIOR.RERAISE)
                run_pre_post_commands('pre_test', [mongodb_setup_config, test_control_config, test],
                                      config, EXCEPTION_BEHAVIOR.RERAISE, test['id'])
                background_tasks = start_background_tasks(config, test, test['id'])

                if test_delay_seconds:
                    LOG.info("Sleeping for %s seconds before test %s", test_delay_seconds,
                             test['id'])
                    time.sleep(test_delay_seconds)

                LOG.info("Starting test %s", test['id'])
                timer = {}
                timer['start'] = time.time()
                # Run the actual task
                run_test(test, config)
                timer['end'] = time.time()

            finally:
                stop_background_tasks(background_tasks)
                if 'skip_validate' not in test or not test['skip_validate']:
                    run_validate(config, test['id'])
                run_pre_post_commands('post_test',
                                      [test, test_control_config, mongodb_setup_config], config,
                                      EXCEPTION_BEHAVIOR.CONTINUE, test['id'])

            # Parse test output (on successful test exit)
            LOG.info("After successful test run for test %s. Parsing results now", test['id'])
            parse_test_results(test, config, timer)

    finally:
        run_pre_post_commands('post_task', [test_control_config, mongodb_setup_config], config,
                              EXCEPTION_BEHAVIOR.CONTINUE)
        # Set perf.json to 555
        # Todo: replace with os.chmod call or remove in general
        # Previously this was set to 777. I can't come up with a good reason.
        subprocess.check_call(['chmod', '555', 'perf.json'])
        legacy_copy_perf_output()


def call_workload_setup():
    """
    This ensures we call workload_setup.py before the real logic of
    test_control.py.

    Older revisions of the `mongo` repo don't call `workload_setup.py`
    in their evergreen config. We call it here for
    backward-compatibility with such commits.

    PERF-1250: After SERVER-32260 and its backports, sys-perf will
    call workload_setup explicitly, obviating the need for this call.
    This call and matching function should be deleted a respectful
    period of time after that work is done.
    """
    workload_setup_config = ConfigDict('workload_setup')
    workload_setup_config.load()
    setup = WorkloadSetupRunner(workload_setup_config)
    if not setup.already_done():
        setup.setup_workloads()
    workload_setup_config.save()


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
    common.log.setup_logging(args.debug, args.log_file)

    # See comment on call_workload_setup
    call_workload_setup()

    config = ConfigDict('test_control')
    config.load()
    run_tests(config)


if __name__ == '__main__':
    main(sys.argv[1:])
