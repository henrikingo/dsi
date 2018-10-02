#!/usr/bin/env python2.7
""" Test runner in DSI Framework """

from __future__ import print_function

import argparse

import logging
import os
import shutil
import subprocess
import sys
import threading
import time
import yaml

from nose.tools import nottest

from common.exit_status import write_exit_status, ExitStatus, EXIT_STATUS_OK
from common.utils import mkdir_p
from common.config import ConfigDict
from common.host_utils import extract_hosts, setup_ssh_agent
from common.command_runner import run_pre_post_commands, EXCEPTION_BEHAVIOR, prepare_reports_dir
from common.host_factory import make_host
from common.host import INFO_ADAPTER
from common.jstests import run_validate
import common.log
from common.workload_output_parser import parse_test_results, validate_config
from workload_setup import WorkloadSetupRunner

LOG = logging.getLogger(__name__)


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
    client_host = common.command_runner.make_workload_runner_host(config)

    no_output_timeout_ms = config['test_control']['timeouts']['no_output_ms']

    # Generate and upload the test's configuration file if there is one
    generate_config_file(test, directory, client_host)

    with open(filename, 'wb+', 0) as out:
        safe_out = common.log.UTF8WrapperStream(out)
        tee_out = common.log.TeeStream(INFO_ADAPTER, safe_out)
        try:
            exit_status = client_host.exec_command(
                test['cmd'],
                stdout=tee_out,
                stderr=tee_out,
                no_output_timeout_ms=no_output_timeout_ms,
                get_pty=True)
            error = ExitStatus(exit_status, test['cmd'])
        except Exception as e:  # pylint: disable=broad-except
            error = get_error_from_exception(e)

        write_exit_status(tee_out, error)

    # Automatically retrieve output files, if specified, and put them into the reports directory
    if 'output_files' in test:
        for output_file in test['output_files']:
            client_host.retrieve_path(output_file,
                                      os.path.join(directory, os.path.basename(output_file)))
    client_host.close()

    if error.status != EXIT_STATUS_OK:
        raise subprocess.CalledProcessError(error.status, test['id'], output=error.message)


def get_error_from_exception(exception):
    """ create an error object from an exception.

    :param Exception exception: the exception instance.
    :returns: ErrorStatus containing the error message and status.
    """
    if isinstance(exception, subprocess.CalledProcessError):
        status = exception.returncode  # pylint: disable=no-member
        output = exception.output  # pylint: disable=no-member
    else:
        status = 1
        output = repr(exception)
    return ExitStatus(status, output)


# pylint: disable=too-many-branches,too-many-statements,too-many-nested-blocks
@nottest
def run_tests(config):
    """Main logic to run tests

    :return: True if all tests passed
    """
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

    # array containing the status of each test
    statuses = []

    try:
        if os.path.exists('perf.json'):
            os.remove('perf.json')
            LOG.warning("Found old perf.json file. Overwriting.")

        for index, test in enumerate(test_control_config['run']):
            # the exit code for the current test
            error = False
            background_tasks = []
            LOG.info('running test %s', test)
            timer = {}
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
                timer['start'] = time.time()
                # Run the actual task
                run_test(test, config)
            except:  # pylint: disable=bare-except
                LOG.error("test %s failed.", test['id'], exc_info=1)
                error = True

            timer['end'] = time.time()

            try:
                stop_background_tasks(background_tasks)
                if 'skip_validate' not in test or not test['skip_validate']:
                    run_validate(config, test['id'])
                run_pre_post_commands('post_test',
                                      [test, test_control_config, mongodb_setup_config], config,
                                      EXCEPTION_BEHAVIOR.CONTINUE, test['id'])
            except:  # pylint: disable=bare-except
                LOG.error("Post-test activities failed after test %s.", test['id'], exc_info=1)
                error = True

            statuses.append(error)
            if error:
                LOG.warn("Unsuccessful test run for test %s. Parsing results now", test['id'])
            else:
                LOG.info("Successful test run for test %s. Parsing results now", test['id'])
            parse_test_results(test, config, timer)

    finally:
        run_pre_post_commands('post_task', [test_control_config, mongodb_setup_config], config,
                              EXCEPTION_BEHAVIOR.CONTINUE)
        # Set perf.json to 555
        # Todo: replace with os.chmod call or remove in general
        # Previously this was set to 777. I can't come up with a good reason.
        subprocess.check_call(['chmod', '555', 'perf.json'])
        legacy_copy_perf_output()

    LOG.info("%s of %s tests exited with an error.", sum(statuses), len(statuses))
    return all(statuses)


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
    """ Main function. Parse command line options, and run tests.

    :returns: int the exit status to return to the caller (0 for OK)
    """
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
    error = run_tests(config)
    return 0 if not error else 1


if __name__ == '__main__':
    exit_code = main(sys.argv[1:])  # pylint: disable=invalid-name
    if exit_code != 0:
        LOG.error("main() call failed: exiting with %s", exit_code)
    # test_control needs to return 0 or evergreen will skip all subsequent steps (like
    # upload, analysis etc.)
    sys.exit(0)
