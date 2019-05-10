"""
Test runners for different types of test frameworks.
"""

from __future__ import print_function

import os
import subprocess

from nose.tools import nottest

import common.log
import common.utils

from common.exit_status import StatusWithMessage, EXIT_STATUS_LINE_PREFIX
from common.host import INFO_ADAPTER


class _BaseRunner(object):
    """
    Base class for a test runner. Runners are mapped to performance testing frameworks.
    (e.g. YCSB, LinkBench).

    There is a catch-all _ShellRunner for running shell commands of frameworks that
    don't have their own dedicated runners.
    """

    def __init__(self, test_name=None, output_files=None, is_production=None, timeout=None):
        """
        :param test_name: the name of the test suite. obtained from test_control.id.
        :param output_files: the list of output files a test suite generates. Used for uploading
                             after the test runs. Some test suites have a default list of
                             output files in addition to what's specified here.
        :param is_production: whether this test is running in production or locally.
        :param timeout: test timeout
        """
        self.report_dir = os.path.join('reports', test_name)
        common.utils.mkdir_p(self.report_dir)

        self.report_file_name = os.path.join(self.report_dir, 'test_output.log')

        self.output_files = output_files
        self.is_production = is_production
        self.timeout = timeout

    def run(self, host):
        """
        Run a test.

        :rtype: StatusWithMessage
        :param host: Host object to run this test on
        :return: status of the command run
        """
        with open(self.report_file_name, 'wb+', 0) as out:
            safe_out = common.log.UTF8WrapperStream(out)
            tee_out = common.log.TeeStream(INFO_ADAPTER, safe_out)
            try:
                status = self._do_run(host, tee_out)
            except subprocess.CalledProcessError as e:
                status = StatusWithMessage(e.returncode, e.output)
            except Exception as e:  # pylint: disable=broad-except
                status = StatusWithMessage(1, repr(e))

            self._log_status(tee_out, status)

        self._retrieve_test_output(host)

        return status

    @property
    def numactl_prefix(self):
        """
        Bind a process to a single CPU socket but use RAM connected to all sockets.

        This configuration is duplicated in YAML as infrastructure_provisioning.numactl_prefix
        """
        return 'numactl --interleave=all --cpunodebind=1'

    @staticmethod
    def get_default_output_files():
        """
        Get the default output files for generating perf.json.

        :return: list of default metrics files. Individual workloads can add their own
        but they won't be used for perf.json.
        """
        return []

    def _do_run(self, host, out):  # pylint: disable=unused-argument
        raise ValueError('run method must be implemented by the subclass: ',
                         self.__class__.__name__)

    def _retrieve_test_output(self, host):
        for output_file in self.output_files:
            # TODO: TIG-1130: if remote file doesn't exist, this will silently fail
            host.retrieve_path(output_file,
                               os.path.join(self.report_dir, os.path.basename(output_file)))

    @staticmethod
    def _log_status(stream, exit_status):
        stream.write("\n{} {} '{}'\n".format(EXIT_STATUS_LINE_PREFIX, exit_status.status,
                                             exit_status.message.encode('string_escape')))
        stream.flush()


class _ShellRunner(_BaseRunner):
    def __init__(self, test_cmd, **kwargs):
        super(_ShellRunner, self).__init__(**kwargs)
        self.test_cmd = test_cmd

    def _do_run(self, host, out):
        exit_code = host.exec_command(
            self.test_cmd, stdout=out, stderr=out, no_output_timeout_ms=self.timeout, get_pty=True)
        return StatusWithMessage(exit_code, self.test_cmd)


class GennyRunner(_BaseRunner):
    """
    Class for running genny tests.
    """

    def __init__(self, workload_config, db_url, **kwargs):
        super(GennyRunner, self).__init__(**kwargs)
        self.workload_config = workload_config
        self.db_url = db_url

        # Append the default genny output files. Individual instances of
        # genny workloads may generate more output files.
        #
        # The JSON report for the perf plugin must come first to play nice
        # with the workload output parser.
        self.output_files = self.get_default_output_files()

    @staticmethod
    def get_default_output_files():
        """
        See _BaseRunner.get_default_output_files()
        """
        return ['data/genny-perf.json', 'data/genny-perf.csv', 'data/genny-cedar-report.json']

    def _do_run(self, host, out):
        commands = [
            'mkdir -p metrics',
            '{} genny/bin/genny run -u "{}" -m cedar-csv -o ./genny-perf.csv {}'.format(
                self.numactl_prefix, self.db_url, self.workload_config),
            'genny-metrics-legacy-report --report-file genny-perf.json genny-perf.csv'
        ]

        if self.is_production:
            # Only generate the cedar report in production. The Cedar certificates are
            # not available elsewhere.
            commands.append('genny-metrics-report --report-file genny-cedar-report.json '
                            'genny-perf.csv metrics')

        for command in commands:
            # Write the output of genny to the ephemeral drive (mounted on ~/data)
            # to ensure it has enough disk space.
            command = 'cd ./data; ' + command

            exit_code = host.exec_command(
                command, stdout=out, stderr=out, no_output_timeout_ms=self.timeout, get_pty=True)

            # Fail early and log the exact command that failed.
            if exit_code:
                return StatusWithMessage(exit_code, command)

        # Log a short message on success.
        return StatusWithMessage(0, 'GennyRunner.run()')


class GennyCanariesRunner(_BaseRunner):
    """
    Class for running Genny performance self tests.
    """

    def __init__(self, db_url, **kwargs):
        super(GennyCanariesRunner, self).__init__(**kwargs)
        self.db_url = db_url
        self.output_files = self.get_default_output_files()

    @staticmethod
    def get_default_output_files():
        """
        See _BaseRunner.get_default_output_files()
        """
        return ['data/nop.csv', 'data/ping.csv']

    def _do_run(self, host, out):
        commands = [
            'genny/bin/genny-canaries nop -o nop.csv',
            'genny/bin/genny-canaries ping -u "{}" -i 10000 -o ping.csv'.format(self.db_url),
        ]

        for command in commands:
            # Write the output of genny to the ephemeral drive (mounted on ~/data)
            # to ensure it has enough disk space.
            command = '{} && {} {}'.format('cd ./data', self.numactl_prefix, command)

            exit_code = host.exec_command(
                command, stdout=out, stderr=out, no_output_timeout_ms=self.timeout, get_pty=True)

            # Fail early and log the exact command that failed.
            if exit_code:
                return StatusWithMessage(exit_code, command)

        # Log a short message on success.
        return StatusWithMessage(0, 'GennyCanariesRunner.run()')


@nottest
def get_test_runner(test_config, god_config):
    """
    Get the test runner for a given test type.

    :rtype: _BaseRunner
    :param test_config: config dictionary for this test.
    :param god_config: top-level config dictionary.
    :return: an instance of a _BaseRunner subclass.
    """
    # Options from test_config.
    name = test_config['id']
    test_type = test_config['type']
    output_files = test_config.get('output_files', [])

    # Options from god_config.
    is_production = god_config['bootstrap']['production']
    timeout = god_config['test_control']['timeouts']['no_output_ms']

    runner_config = {
        'test_name': name,
        'output_files': output_files,
        'is_production': is_production,
        'timeout': timeout
    }

    db_url = god_config['mongodb_setup']['meta']['mongodb_url']

    if test_type == 'genny':
        workload_config_path = test_config['config_filename']
        return GennyRunner(workload_config_path, db_url, **runner_config)
    elif test_type == 'genny_canaries':
        return GennyCanariesRunner(db_url, **runner_config)

    return _ShellRunner(test_config['cmd'], **runner_config)