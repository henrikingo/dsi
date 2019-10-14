"""
Tests for bin/test_runner.py
"""
import os
import shutil
import subprocess
import tempfile
import unittest

from mock import Mock, call

from common.remote_host import RemoteHost

from testcontrollib import test_runner
from testcontrollib.test_runner import get_test_runner


class GetTestRunnerTestCase(unittest.TestCase):
    """
    Test for test_runner.get_test_runner()
    """
    def setUp(self):
        self.get_test_config = lambda kind: {
            'id': 'dummy_test',
            'type': kind,
            'cmd': 'dummy shell command',
            'config_filename': 'dummy_config_filename',
            'output_files': ['output_file1', 'output_file2']
        }

        self.get_test_control_config = lambda prod=True, numa='numactl --interleave=all --cpunodebind=1': {
            'mongodb_url': 'dummy_mongodb_url',
            'is_production': prod,
            'timeouts': {
                'no_output_ms': 100
            },
            'numactl_prefix_for_workload_client': numa
        }

        # Change to a temporary directory for this test because the report
        # file is generated as a relative path to the CWD.
        self.original_cwd = os.getcwd()
        self.tempdir = tempfile.mkdtemp()
        os.chdir(self.tempdir)

    def tearDown(self):
        os.chdir(self.original_cwd)
        shutil.rmtree(self.tempdir)

    def call_runner_run(self, runner, success_report_str, output_file_calls):
        mock_host = Mock(spec=RemoteHost)
        report_file = os.path.join(self.tempdir, 'reports', 'dummy_test', 'test_output.log')

        def wrapper(host, exit_code, report_str):
            status = runner.run(host)
            self.assertEqual(status.status, exit_code)
            with open(report_file) as file_handler:
                self.assertEqual(file_handler.read(), report_str)
            mock_host.retrieve_path.assert_has_calls(output_file_calls)

        # Test happy case.
        mock_host.exec_command = Mock(return_value=0)
        mock_host.retrieve_path = Mock()
        wrapper(mock_host, 0, success_report_str)

        # Test CalledProcessError
        mock_error = subprocess.CalledProcessError(42, 'dummy_cmd', 'dummy_msg')
        mock_host.exec_command = Mock(side_effect=mock_error)
        mock_host.retrieve_path = Mock()
        wrapper(mock_host, 42, '\nexit_status: 42 \'dummy_msg\'\n')

        # Test Unknown Exception
        mock_error = ValueError('Unknown Error')
        mock_host.exec_command = Mock(side_effect=mock_error)
        mock_host.retrieve_path = Mock()
        wrapper(mock_host, 1, '\nexit_status: 1 \'ValueError(\\\'Unknown Error\\\',)\'\n')

    def test_get_shell_runner(self):
        """
        Can get the shell test runner for unknown test kinds.
        """
        runner = get_test_runner(self.get_test_config('unknown'), self.get_test_control_config())
        self.assertIsInstance(runner, test_runner._ShellRunner)
        output_file_calls = [
            call('output_file1', 'reports/dummy_test/output_file1'),
            call('output_file2', 'reports/dummy_test/output_file2')
        ]
        report_str = '\nexit_status: 0 \'dummy shell command\'\n'

        self.call_runner_run(runner, report_str, output_file_calls)

    def test_get_genny_runner(self):
        """
        Can get the genny test runner for "genny" tests.
        """
        runner = get_test_runner(self.get_test_config('genny'), self.get_test_control_config())
        self.assertIsInstance(runner, test_runner.GennyRunner)

        report_str = '\nexit_status: 0 \'GennyRunner.run()\'\n'
        output_file_calls = [
            call('data/genny-perf.json', 'reports/dummy_test/genny-perf.json'),
            call('data/genny-perf.csv', 'reports/dummy_test/genny-perf.csv'),
            call('data/genny-cedar-report.json', 'reports/dummy_test/genny-cedar-report.json')
        ]
        self.call_runner_run(runner, report_str, output_file_calls)

    def test_get_genny_canaries_runner(self):
        """
        Can get the genny test runner for "genny" tests.
        """
        runner = get_test_runner(self.get_test_config('genny_canaries'),
                                 self.get_test_control_config())
        self.assertIsInstance(runner, test_runner.GennyCanariesRunner)

        report_str = '\nexit_status: 0 \'GennyCanariesRunner.run()\'\n'
        output_file_calls = [
            call('data/nop.csv', 'reports/dummy_test/nop.csv'),
            call('data/ping.csv', 'reports/dummy_test/ping.csv')
        ]
        self.call_runner_run(runner, report_str, output_file_calls)

    def test_genny_runner_run(self):
        """
        Check that GennyRunner calls the correct shell commands. Do the check multiple times,
        for different configurations.

        Any changes to genny's invocation will require updating this test.
        """
        # Local Environment
        runner = get_test_runner(self.get_test_config('genny'), self.get_test_control_config(False))
        call_args = [
            'cd ./data; mkdir -p metrics',
            ('cd ./data; numactl --interleave=all --cpunodebind=1 genny/bin/genny run '
             '-u "dummy_mongodb_url" -m cedar-csv -o ./genny-perf.csv dummy_config_filename'),
            'cd ./data; genny-metrics-legacy-report --report-file genny-perf.json genny-perf.csv',
        ]
        mock_host = Mock(spec=RemoteHost)
        mock_host.exec_command = Mock(return_value=0)
        runner.run(mock_host)
        call_args_iter = iter(call_args)
        for arg in mock_host.exec_command.call_args_list:
            self.assertEqual(arg[0][0], next(call_args_iter))

        # Production Environment
        runner = get_test_runner(self.get_test_config('genny'), self.get_test_control_config(False))
        args = call_args[:]
        args.append('cd ./data; genny-metrics-report --report-file '
                    'genny-cedar-report.json genny-perf.csv metrics')
        mock_host.exec_command = Mock(return_value=0)
        runner.run(mock_host)
        call_args_iter = iter(args)
        for arg in mock_host.exec_command.call_args_list:
            self.assertEqual(arg[0][0], next(call_args_iter))

        # No numactl.
        runner = get_test_runner(self.get_test_config('genny'),
                                 self.get_test_control_config(False, ''))
        args = call_args[:]
        args[1] = (
            'cd ./data;  genny/bin/genny run -u "dummy_mongodb_url" -m cedar-csv -o ./genny-perf.csv '
            'dummy_config_filename')  # Remove the numactl line.
        mock_host.exec_command = Mock(return_value=0)
        runner.run(mock_host)
        call_args_iter = iter(args)
        for arg in mock_host.exec_command.call_args_list:
            self.assertEqual(arg[0][0], next(call_args_iter))
