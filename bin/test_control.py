#!/usr/bin/env python2.7
""" Test runner in DSI Framework """

from __future__ import print_function

import argparse

import logging
import os
import shutil
import subprocess
import sys
import time
import yaml

from nose.tools import nottest

from common.exit_status import EXIT_STATUS_OK
from common.config import ConfigDict
from common.host_utils import extract_hosts, setup_ssh_agent
from common.command_runner import run_pre_post_commands, EXCEPTION_BEHAVIOR, prepare_reports_dir
from common.jstests import run_validate
import common.log
import common.cedar as cedar
from common.workload_output_parser import parse_test_results, validate_config

from testcontrollib import test_runner

LOG = logging.getLogger(__name__)


def legacy_copy_perf_output():
    """Put perf.json in the legacy place for backward compatibility"""
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
                    # pylint: disable=eval-used
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
            host = next((host for host in hosts if name.endswith(host.public_ip)), None)
            if host:
                source = os.path.join(root, name)
                alias = "{category}.{offset}".format(category=host.category, offset=host.offset)

                destination = "{}-{}".format(
                    os.path.basename(source).split('--')[0], os.path.basename(root))
                destination = os.path.join('reports', alias, destination)
                shutil.copyfile(source, destination)


@nottest
def run_test(test, config):
    """
    Run one test. This creates a Host object, runs the command, and saves the output to a file.

    :param test ConfigDict: The ConfigDict object for the test to run
    :param config ConfigDict: The top level ConfigDict
    """
    runner = test_runner.get_test_runner(test, config['test_control'])
    client_host = common.command_runner.make_workload_runner_host(config)

    # Generate and upload the test's configuration file if there is one.
    generate_config_file(test, runner.report_dir, client_host)

    status = runner.run(client_host)

    client_host.close()

    if status.status != EXIT_STATUS_OK:
        raise subprocess.CalledProcessError(status.status, test['id'], output=status.message)

    return status


class TestStatus(object):
    """Status of this script."""
    FAILED = 'failed'
    SUCCESS = 'succeeded'
    ERROR = 'failed with unknown error'


# pylint: disable=too-many-branches,too-many-statements,too-many-nested-blocks
@nottest
def run_tests(config):
    """Main logic to run tests

    :return: True if all tests failed or an error occurred.
             No more tests are run when an error is encountered.
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

    num_tests_run = 0
    num_tests_failed = 0

    # cedar reporting
    report = cedar.Report(config.get('runtime'))

    # Default the status to ERROR to catch unexpected failures.
    # If a tests succeeds, the status is explicitly set to SUCCESS.
    cur_test_status = TestStatus.ERROR

    try:
        if os.path.exists('perf.json'):
            os.remove('perf.json')
            LOG.warning("Found old perf.json file. Overwriting.")

        for test in test_control_config['run']:
            LOG.info('running test %s', test)
            timer = {}
            try:
                # Only run between_tests after the first test.
                if num_tests_run > 0:
                    run_pre_post_commands('between_tests',
                                          [mongodb_setup_config, test_control_config], config,
                                          EXCEPTION_BEHAVIOR.RERAISE)
                run_pre_post_commands('pre_test', [mongodb_setup_config, test_control_config, test],
                                      config, EXCEPTION_BEHAVIOR.RERAISE, test['id'])

                if test_delay_seconds:
                    LOG.info("Sleeping for %s seconds before test %s", test_delay_seconds,
                             test['id'])
                    time.sleep(test_delay_seconds)

                LOG.info("Starting test %s", test['id'])
                timer['start'] = time.time()
                # Run the actual test
                run_test(test, config)
            except subprocess.CalledProcessError:
                LOG.error("test %s failed.", test['id'], exc_info=1)
                cur_test_status = TestStatus.FAILED
            except:  # pylint: disable=bare-except
                LOG.error("Unexpected failure in test %s.", test['id'], exc_info=1)
                cur_test_status = TestStatus.ERROR
            else:
                cur_test_status = TestStatus.SUCCESS

            num_tests_run += 1
            timer['end'] = time.time()

            try:
                if 'skip_validate' not in test or not test['skip_validate']:
                    run_validate(config, test['id'])
                run_pre_post_commands('post_test',
                                      [test, test_control_config, mongodb_setup_config], config,
                                      EXCEPTION_BEHAVIOR.CONTINUE, test['id'])
            except:  # pylint: disable=bare-except
                # The post test activities failing implies the test failing.
                LOG.error("Post-test activities failed after test %s.", test['id'], exc_info=1)

                # Don't "downgrade" from ERROR to FAILED.
                if cur_test_status != TestStatus.ERROR:
                    cur_test_status = TestStatus.FAILED

            if cur_test_status == TestStatus.FAILED:
                num_tests_failed += 1
                LOG.warn("Unsuccessful test run for test %s. Parsing results now", test['id'])
            elif cur_test_status == TestStatus.ERROR:
                LOG.warn("Unknown error in test %s, exiting early.", test['id'])
                break
            else:
                LOG.info("Successful test run for test %s. Parsing results now", test['id'])

            _, cedar_test = parse_test_results(test, config, timer)
            report.add_test(cedar_test)
    except Exception as e:  # pylint: disable=broad-except
        LOG.error('Unexcepted exception: %s', repr(e), exc_info=1)
    finally:
        report.write_report()
        run_pre_post_commands('post_task', [test_control_config, mongodb_setup_config], config,
                              EXCEPTION_BEHAVIOR.CONTINUE)
        # Set perf.json to 555
        # Todo: replace with os.chmod call or remove in general
        # Previously this was set to 777. I can't come up with a good reason.
        subprocess.check_call(['chmod', '555', 'perf.json'])
        legacy_copy_perf_output()

    LOG.info("%s of %s tests exited with an error.", num_tests_failed, num_tests_run)

    # Return True if all tests failed or if the last test errored.
    return (num_tests_run == num_tests_failed) or (cur_test_status == TestStatus.ERROR)


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

    config = ConfigDict('test_control')
    config.load()

    error = run_tests(config)
    return 1 if error else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
