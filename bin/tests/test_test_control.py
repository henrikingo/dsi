"""
Tests for bin/test_control.py
"""

import copy
import logging
import os
import re
import shutil
import subprocess
import unittest

from mock import patch, mock_open, Mock, call
from testfixtures import LogCapture

import common.host_utils
from common.command_runner import EXCEPTION_BEHAVIOR
from common.command_runner import print_trace
from common.command_runner import run_pre_post_commands
from common.config import ConfigDict
from common.remote_host import RemoteHost
from common.utils import mkdir_p
from test_control import BackgroundCommand, start_background_tasks
from test_control import copy_timeseries
from test_control import get_error_from_exception, ExitStatus
from test_control import run_test
from test_control import run_tests
from test_lib.fixture_files import FixtureFiles

FIXTURE_FILES = FixtureFiles(os.path.dirname(__file__))


class RunTestsTestCase(unittest.TestCase):
    """
    Unit Test for test_control.run_tests
    """
    def setUp(self):
        """Create a dict that looks like a ConfigDict object """
        self.config = {
            'infrastructure_provisioning': {
                'tfvars': {
                    'ssh_user': 'test_ssh_user',
                    'ssh_key_file': 'mock/ssh/key/file'
                },
                'out': {
                    'mongod': [
                        {'public_ip': '53.1.1.1',
                         'private_ip': '10.2.1.1'},
                        {'public_ip': '53.1.1.9',
                         'private_ip': '10.2.1.9'}
                    ],
                    'mongos': [
                        {'public_ip': '53.1.1.102',
                         'private_ip': '10.2.1.102'}
                    ],
                    'configsvr': [
                        {'public_ip': '53.1.1.53',
                         'private_ip': '10.2.1.53'}
                    ],
                    'workload_client': [
                        {'public_ip': '53.1.1.101',
                         'private_ip': '10.2.1.200'}
                    ]
                }
            },
            'mongodb_setup': {
                'post_test': [
                    {'on_all_servers': {
                        'retrieve_files': {
                            'data/logs/': './'}
                        }
                    },
                    {'on_mongod': {
                        'retrieve_files': {
                            'data/dbs/diagnostic.data': './diagnostic.data'}
                        }
                    },
                    {'on_configsvr': {
                        'retrieve_files': {
                            'data/dbs/diagnostic.data': './diagnostic.data'}
                        }
                    }
                ],
                'mongod_config_file': {
                    'storage': {
                        'engine': 'wiredTiger'
                    }
                }
            },
            'runtime': {
                'task_id': 'STAY IN YOUR VEHICLE CITIZEN'
            },
            'test_control': {
                'task_name': 'test_config',
                'reports_dir_basename': 'reports',
                'perf_json': {
                    'path': 'perf.json'
                },
                'output_file': {
                    'mongoshell': 'test_output.log',
                    'ycsb': 'test_output.log',
                    'fio': 'fio.json',
                    'iperf': 'iperf.json'
                },
                'timeouts': {
                    'no_output_ms': 5000,
                },
                'run': [
                    {'id': 'benchRun',
                     'type': 'shell',
                     'cmd': '$DSI_PATH/workloads/run_workloads.py -c workloads.yml',
                     'config_filename': 'workloads.yml',
                     'output_files': ['mock_output0.txt', 'mock_output0.txt'],
                     'workload_config': 'mock_workload_config'
                    },
                    {'id': 'ycsb_load',
                     'type': 'ycsb',
                     'cmd': 'cd YCSB/ycsb-mongodb; ./bin/ycsb load mongodb -s -P ' +
                            'workloads/workloadEvergreen -threads 8; sleep 1;',
                     'config_filename': 'workloadEvergreen',
                     'workload_config': 'mock_workload_config',
                     'skip_validate': True
                    },
                    {'id': 'fio',
                     'type': 'fio',
                     'cmd': './fio-test.sh some_hostname',
                     'skip_validate': True
                    }
                ],
                'jstests_dir': './jstests/hooks',
                'post_test': [
                    {'on_workload_client': {
                        'retrieve_files': {
                            'workloads/workload_timestamps.csv': '../workloads_timestamps.csv'}
                        }
                    }
                ],
                'out': {'exit_codes': {}},
                'dsisocket': {'enabled': False, 'bind_addr': '127.0.0.1', 'port': 27007}
            }
        } # yapf: disable
        self.reports_container = FIXTURE_FILES.fixture_file_path('container')
        self.reports_path = os.path.join(self.reports_container, 'reports_tests')

        mkdir_p(self.reports_path)

    def tearDown(self):
        shutil.rmtree(self.reports_container)
        if os.path.exists('test_control.out.yml'):
            os.remove('test_control.out.yml')

    @patch('os.walk')
    @patch('test_control.extract_hosts')
    @patch('shutil.copyfile')
    def test_copy_timeseries(self, mock_copyfile, mock_hosts, mock_walk):
        """ Test run RunTest.copy_timeseries. """

        mock_walk.return_value = []
        mock_hosts.return_value = []
        copy_timeseries(self.config)
        self.assertFalse(mock_copyfile.called)

        mock_walk.return_value = []
        mock_hosts.return_value = []
        copy_timeseries(self.config)
        self.assertFalse(mock_copyfile.called)

        mock_walk.reset_mock()
        mock_hosts.reset_mock()
        mock_copyfile.reset_mock()

        mock_walk.return_value = [
            ('/dirpath', ('dirnames', ), ()),
        ]

        dummy_host_info = common.host_utils.HostInfo(public_ip='10.0.0.0',
                                                     category='mongod',
                                                     offset=0)

        mock_hosts.return_value = [dummy_host_info]

        copy_timeseries(self.config)
        self.assertFalse(mock_copyfile.called)

        mock_walk.reset_mock()
        mock_hosts.reset_mock()
        mock_copyfile.reset_mock()
        mock_walk.return_value = [
            ('/dirpath', ('dirnames', ), ('baz', )),
        ]
        mock_hosts.return_value = [dummy_host_info]

        copy_timeseries(self.config)
        self.assertFalse(mock_copyfile.called)

        mock_walk.reset_mock()
        mock_hosts.reset_mock()
        mock_copyfile.reset_mock()
        mock_walk.return_value = [
            ('/dirpath', ('dirnames', ), ('10.0.0.0--notmatching', )),
            ('/foo/bar', (), ('spam', 'eggs')),
        ]
        mock_hosts.return_value = [dummy_host_info]

        copy_timeseries(self.config)
        self.assertFalse(mock_copyfile.called)

        mock_walk.reset_mock()
        mock_hosts.reset_mock()
        mock_copyfile.reset_mock()
        mock_walk.return_value = [
            ('/dirpath', ('dirnames', ), ('matching--10.0.0.0', )),
        ]
        mock_hosts.return_value = [dummy_host_info]

        copy_timeseries(self.config)
        self.assertTrue(
            mock_copyfile.called_with('/dirpath/matching--10.0.0.0',
                                      'reports/mongod.0/matching-dirpath'))

        mock_walk.reset_mock()
        mock_hosts.reset_mock()
        mock_copyfile.reset_mock()
        mock_walk.return_value = [
            ('/dirpath0', ('dirnames0', ), ('file0--10.0.0.0', )),
            ('/dirpath1', ('dirnames1', ), ('file1--10.0.0.1', )),
            ('/dirpath2', ('dirnames2', ), ('file2--10.0.0.2', )),
        ]
        mock_hosts.return_value = [dummy_host_info, dummy_host_info]

        copy_timeseries(self.config)
        self.assertTrue(mock_copyfile.called)
        self.assertTrue(
            mock_copyfile.called_with('/dirpath0/file0--10.0.0.0',
                                      'reports/mongod.0/matching-dirpath0'))
        self.assertTrue(
            mock_copyfile.called_with('/dirpath1/file1--10.0.0.1',
                                      'reports/mongod.1/matching-dirpath1'))

    @patch('types.FrameType')
    def test_print_trace_mock_exception(self, mock_frame):
        """ Test test_control.print_trace with mock frame and mock exception"""
        with LogCapture() as log_capture:
            mock_frame.f_locals = {
                'value': 'mock_value',
                'target': 'on_mock_key',
                'command': 'mock_command'
            }
            mock_trace = ((None, None, None, "mock_top_function"), (mock_frame, None, None, None),
                          (mock_frame, None, None, "run_host_command"), (None, "mock_file", -1,
                                                                         "mock_bottom_function"))
            mock_exception = Exception("mock_exception")
            print_trace(mock_trace, mock_exception)
            error_msg = "Exception originated in: mock_file:mock_bottom_function:-1\n"
            error_msg = error_msg + "Exception msg: mock_exception\nmock_top_function:\n    "
            error_msg = error_msg + "in task: on_mock_key\n        in command: mock_command"
        list_errors = list(log_capture.actual())
        self.assertEqual(error_msg, list_errors[0][2])

    @patch('paramiko.SSHClient')
    @patch('common.host_utils.extract_hosts', return_value=(-1, -1))
    def help_trace_function(self, mock_function, mock_command_dicts, mock_extract_hosts, mock_ssh):
        """
        Test test_control.print_trace by calling run_pre_post_commands with a 'pre_task' key, with a
        forced exception. This is a helper function used by other tests within this class. It uses
        a mocked RemoteHost along with a mocked function within the RemoteHost that has a forced
        exception in it.
        :param MagicMock() mock_function: mocked function from mock_remote_host
        :param list(ConfigDict) mock_command_dicts: List of ConfigDict objects that have a
        'pre_task' key.
        :param MagicMock() mock_extract_hosts: DO NOT INPUT IN FUNCTION, patch decorator already
        inputs this argument into the function
        :param MagicMock() mock_ssh: DO NOT INPUT IN FUNCTION, patch decorator already inputs this
        argument into the function
        """
        mock_config = {
            'infrastructure_provisioning': {
                'tfvars': {
                    'ssh_user': 'mock_ssh_user',
                    'ssh_key_file': 'mock_ssh_key'
                }
            },
            'mongodb_setup': {
                'meta': {
                    'net': {},
                },
                'authentication': {
                    'enabled': True,
                    'username': 'username',
                    'password': 'password',
                },
            },
        }
        with LogCapture(level=logging.ERROR) as log_capture:
            # LogCapture captures all log output into the object log_capture. level specifies which
            # log level to detect. logging.ERROR will cause log_capture to only contain logs
            # outputted with the ERROR level or higher. The patch on common.host_factory.make_host
            # mocks the function and is called within run_commands:
            # (pre_task -> dispatch_commands -> run_host_command -> make_host)
            # The mock_function.side_effect causes it to raise an Exception causing print_trace
            # to log the proper information. mock_function will be called within run_command or
            # _run_host_command_map depending on mock_command_dicts. run_pre_post_commands exits
            # with code 1 on exception when given EXCEPTION_BEHAVIOR.EXIT, so self.assertRaises()
            # catches this. The asserts check if the mock_function, extract_hosts, and make_host
            # were called along with asserting the error code was 1.
            return_value = RemoteHost(None, None, None)
            # disabling yapf here because pylint and yapf disagree on indentation convention
            # yapf: disable
            with patch(
                    'common.host_factory.make_host', return_value=return_value) as mock_make_host:
                # yapf: enable
                mock_function.side_effect = Exception("Mock Exception")
                with self.assertRaises(SystemExit) as exception:
                    run_pre_post_commands('pre_task', mock_command_dicts, mock_config,
                                          EXCEPTION_BEHAVIOR.EXIT)
                self.assertTrue(mock_function.called)
                self.assertTrue(mock_extract_hosts.called)
                self.assertTrue(mock_make_host.called)
                self.assertTrue(mock_ssh.called)
                self.assertEqual(exception.exception.code, 1)
        task = list(mock_command_dicts[0]['pre_task'][0].keys())[0]
        command = mock_command_dicts[0]['pre_task'][0][task]
        error_regex_str = "Exception originated in: .+"
        error_regex_str = error_regex_str + "\nException msg:.*?"
        error_regex_str = error_regex_str + "\nrun_pre_post_commands:\n    "
        error_regex_str = error_regex_str + "in task: " + task + "\n        "
        error_regex_str = error_regex_str + "in command: " + re.escape(str(command))
        error_pattern = re.compile(error_regex_str)
        list_errors = list(log_capture.actual())  # Get actual string held by loc_capture object
        self.assertRegex(list_errors[0][2], error_pattern)

    @patch('common.remote_host.RemoteHost.upload_file')
    def test_print_trace_upload_file(self, mock_upload_file):
        """ Test test_control.print_trace with exception in upload_file"""
        mock_command_dicts = [{
            'pre_task': [{
                'on_workload_client': {
                    'upload_files': [{
                        'source': 'workloads.tar.gz',
                        'target': 'workloads.tar.gz'
                    }]
                }
            }]
        }, {}]
        self.help_trace_function(mock_upload_file, mock_command_dicts)

    @patch('os.path')
    @patch('common.remote_host.RemoteHost.retrieve_path')
    def test_print_trace_retrieve_path(self, mock_retrieve_path, mock_path):
        """ Test test_control.print_trace with exception in retrieve_path"""
        mock_path.return_value.join.return_value = ""
        mock_path.return_value.normpath.return_value = ""
        mock_command_dicts = [{
            'pre_task': [{
                'on_workload_client': {
                    'retrieve_files': [{
                        'source': 'workloads.tar.gz',
                        'target': 'workloads.tar.gz'
                    }]
                }
            }]
        }, {}]
        self.help_trace_function(mock_retrieve_path, mock_command_dicts)

    @patch('common.remote_host.RemoteHost.create_file')
    def test_print_trace_create_file(self, mock_create_file):
        """ Test test_control.print_trace with exception in create_file"""
        mock_command_dicts = [{
            'pre_task': [{
                'on_workload_client': {
                    'exec_mongo_shell': {
                        'script': 'mock script'
                    }
                }
            }],
        }, {}]
        self.help_trace_function(mock_create_file, mock_command_dicts)

    @patch("common.remote_host.RemoteHost")
    @patch("os.makedirs")
    def test_background_command_run(self, mock_makedirs, mock_host):
        """ Test BackgroundCommand run"""
        subject = BackgroundCommand(mock_host, 'command', 'dirname/basename')

        with patch('test_control.open', mock_open()) as mock_file:
            mock_out = mock_file.return_value
            subject.run()
            mock_file.assert_called_with('dirname/basename', 'wb+', 0)
            mock_makedirs.assert_called_with('dirname')
            mock_host.exec_command.assert_called_with('command',
                                                      stdout=mock_out,
                                                      stderr=mock_out,
                                                      get_pty=True)

    @patch("common.remote_host.RemoteHost")
    def test_background_command_stop(self, mock_host):
        """ Test BackgroundCommand  stop"""
        subject = BackgroundCommand(mock_host, 'command', 'dirname/basename')
        subject.stop()
        mock_host.close.assert_called_once()

    @patch('test_control.make_host')
    @patch('test_control.extract_hosts')
    def test_start_background_tasks(self, mock_extract_hosts, mock_make_host):
        """ Test start_background_tasks"""
        # Add some background tasks to our config
        config = copy.deepcopy(self.config)
        config['test_control']['run'][0]['background_tasks'] = {
            'background_task_one': 'mock_background_task',
            'background_task_two': 'mock_background_task',
            'background_task_three': 'mock_background_task'
        }
        test_id = 'benchRun'

        with patch('test_control.BackgroundCommand'):
            command_dict = config['test_control']['run'][1]
            self.assertEqual(start_background_tasks(config, command_dict, test_id), [])

        with patch('test_control.BackgroundCommand'):
            command_dict = config['test_control']['run'][0]
            mock_make_host.return_value = Mock()
            result = start_background_tasks(config, command_dict, test_id)
            self.assertEqual(len(result), 3)
        mock_extract_hosts.assert_called()

    @patch('test_control.generate_config_file')
    @patch('common.command_runner.make_workload_runner_host')
    @patch('test_control.mkdir_p')
    def test_run_test_exec_command_success(self, mock_mkdir, mock_make_host,
                                           mock_generate_config_file):
        """
        Test test_control.run_test with 0 return value from exec_command (success)
        """
        mock_host = Mock(spec=RemoteHost)
        mock_host.exec_command = Mock(return_value=0)
        mock_make_host.return_value = mock_host
        test = self.config['test_control']['run'][0]
        directory = os.path.join('reports', test['id'])
        with patch('test_control.open', mock_open()):
            run_test(test, self.config)
        mock_mkdir.assert_called_with(directory)
        mock_host.exec_command.assert_called_once()
        mock_generate_config_file.assert_called_once_with(test, directory, mock_host)

        mock_host.exec_command.assert_called()
        mock_host.close.assert_called()
        # These are just throwaway mocks, pylint wants me to do something with them
        mock_mkdir.assert_called()

    @patch('test_control.generate_config_file')
    @patch('common.command_runner.make_workload_runner_host')
    @patch('test_control.mkdir_p')
    def test_run_test_exec_command_failure(self, mock_mkdir, mock_make_host,
                                           mock_generate_config_file):
        """
        Test test_control.run_test with non-zero return value from exec_command (failure)
        """
        # Test with non-zero return value from exec_command
        mock_host = Mock(spec=RemoteHost)
        mock_host.exec_command = Mock(return_value=1)
        mock_make_host.return_value = mock_host
        test = self.config['test_control']['run'][0]
        directory = os.path.join('reports', test['id'])
        with patch('test_control.open', mock_open()):
            self.assertRaises(subprocess.CalledProcessError, run_test, test, self.config)
        mock_host.exec_command.assert_called_once()
        mock_generate_config_file.assert_called_once_with(test, directory, mock_host)
        mock_mkdir.assert_called()

    @patch('test_control.generate_config_file')
    @patch('common.command_runner.make_workload_runner_host')
    @patch('test_control.mkdir_p')
    def test_run_test_output_files(self, mock_mkdir, mock_make_host, mock_generate_config_file):
        """
        Test test_control.run_test with output files specified
        """
        mock_host = Mock(spec=RemoteHost)
        mock_host.exec_command = Mock(return_value=0)
        mock_make_host.return_value = mock_host
        test = self.config['test_control']['run'][0]
        directory = os.path.join('reports', test['id'])
        expected_calls = [call(f, os.path.join(directory, f)) for f in test['output_files']]
        with patch('test_control.open', mock_open()):
            run_test(test, self.config)
        mock_host.retrieve_path.assert_has_calls(expected_calls)
        mock_generate_config_file.assert_called_once_with(test, directory, mock_host)

        mock_host.exec_command.assert_called()
        # These are just throwaway mocks, pylint wants me to do something with them
        mock_host.close.assert_called()
        mock_mkdir.assert_called()

    @patch('test_control.generate_config_file')
    @patch('common.command_runner.make_workload_runner_host')
    @patch('test_control.mkdir_p')
    def test_run_test_get_pty(self, mock_mkdir, mock_make_host, mock_generate_config_file):
        """
        Test test_control.run_test with get_pty=True see PERF-1375
        """
        mock_host = Mock(spec=RemoteHost)
        mock_host.exec_command = Mock(return_value=0)
        mock_make_host.return_value = mock_host
        test = self.config['test_control']['run'][0]
        with patch('test_control.open', mock_open()):
            run_test(test, self.config)
        mock_host.exec_command.assert_called_once()
        self.assertDictContainsSubset({'get_pty': True},
                                      mock_host.exec_command.call_args_list[0][-1])
        mock_generate_config_file.assert_called()
        mock_mkdir.assert_called()

    @patch('test_control.generate_config_file')
    @patch('common.command_runner.make_workload_runner_host')
    @patch('test_control.mkdir_p')
    def test_run_test_no_output_files(self, mock_mkdir, mock_make_host, mock_generate_config_file):
        """
        Test test_control.run_test with no output files specified
        """
        mock_host = Mock(spec=RemoteHost)
        mock_host.exec_command = Mock(return_value=0)
        mock_make_host.return_value = mock_host
        test = self.config['test_control']['run'][1]
        directory = os.path.join('reports', test['id'])
        with patch('test_control.open', mock_open()):
            run_test(test, self.config)
        mock_host.retrieve_path.assert_not_called()
        mock_generate_config_file.assert_called_once_with(test, directory, mock_host)
        mock_mkdir.assert_called()

    # normally wouldn't test internal method, but the collaboration with other
    # objects is complicated within host.exec_command and leads to the core logic
    # being hard to isolate on its own.
    def when_get_error_from_exception(self, case):
        """
        :param case: contains given/then conditions for behavior of _perform_exec

        Example:

            'given': {
                # params given to _perform_exec
                'exception': Exception('cowsay HellowWorld'),
            },
            'then': ErrorStatus(1, 'cowsay HellowWorld')
        """
        given = case['given']
        then = case.get('then', None)

        error = get_error_from_exception(given['exception'])

        self.assertEqual(then, error)

    def test_error_from_exception(self):
        """Test test_control.get_error_from_exception for exception"""
        self.when_get_error_from_exception({
            'given': {
                'exception': Exception('cowsay Hello World'),
            },
            'then': ExitStatus(1, "Exception('cowsay Hello World',)")
        })

    def test_error_from_called_process(self):
        """Test test_control.get_error_from_exception for process error"""
        self.when_get_error_from_exception({
            'given': {
                'exception': subprocess.CalledProcessError(2, 'command', 'process Hello World'),
            },
            'then': ExitStatus(2, "process Hello World")
        })

    # pylint: disable=unused-argument
    @patch('test_control.copy_to_reports')
    @patch('test_control.safe_reset_all_delays')
    @patch('test_control.run_pre_post_commands')
    @patch('test_control.run_test')
    @patch('test_control.parse_test_results', return_value=['status', 'MockParser'])
    @patch('test_control.prepare_reports_dir')
    @patch('subprocess.check_call')
    @patch('test_control.print_perf_json')
    def test_pre_post_commands_ordering(self, mock_copy_perf, mock_check_call, mock_prep_rep,
                                        mock_parse_results, mock_run_test, mock_pre_post,
                                        mock_delays, mock_copy_reports):
        """Test that pre and post commands are called in the right order"""
        real_config_dict = ConfigDict('test_control')
        real_config_dict.raw = self.config
        run_tests(real_config_dict)

        # We will check that the calls to run_pre_post_commands() happened in expected order
        expected_args = [
            'pre_task', 'pre_test', 'post_test', 'between_tests', 'pre_test', 'post_test',
            'between_tests', 'pre_test', 'post_test', 'post_task'
        ]
        observed_args = [args[0][0] for args in mock_pre_post.call_args_list]
        self.assertEqual(expected_args, observed_args)

    # pylint: disable=unused-argument
    @patch('test_control.copy_to_reports')
    @patch('test_control.safe_reset_all_delays')
    @patch('test_control.run_pre_post_commands')
    @patch('test_control.parse_test_results', return_value=('status', ['MockParser']))
    @patch('test_control.prepare_reports_dir')
    @patch('subprocess.check_call')
    @patch('test_control.print_perf_json')
    def test_run_test_exception(self, mock_copy_perf, mock_check_call, mock_prep_rep,
                                mock_parse_results, mock_pre_post, mock_delays, mock_copy_reports):
        """
        Test CalledProcessErrors with cause run_tests return false but other errors will
        cause it to return true
        """
        real_config_dict = ConfigDict('test_control')
        real_config_dict.raw = self.config

        # pylint: disable=bad-continuation
        with patch('test_control.run_test',
                   side_effect=[subprocess.CalledProcessError(99, 'failed-cmd'), 0, 0]):
            utter_failure = run_tests(real_config_dict)
            self.assertFalse(utter_failure)

        with patch('test_control.run_test', side_effect=[ValueError(), 0, 0]):
            utter_failure = run_tests(real_config_dict)
            self.assertTrue(utter_failure)


if __name__ == '__main__':
    unittest.main()
