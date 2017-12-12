"""Tests for bin/common/host.py"""

# pylint: disable=wrong-import-position, wrong-import-order

import copy
import logging
import os
import re
import sys
import unittest

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/common")

import host
from run_test import EXCEPTION_BEHAVIOR
from run_test import copy_timeseries
from run_test import print_trace
from run_test import run_pre_post_commands
from run_test import run_tests

from mock import patch, mock_open, Mock
from testfixtures import LogCapture

from bin.run_test import BackgroundCommand, start_background_tasks


class RunTestTestCase(unittest.TestCase):
    """ Unit Test for Host library """

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
                        {'public_ip': '53.1.1.101'}
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
                ]
            },
            'test_control': {
                'task_name': 'test_config',
                'run': [
                    {'id': 'benchRun',
                     'type': 'shell',
                     'cmd': '$DSI_PATH/workloads/run_workloads.py -c workloads.yml',
                     'config_filename': 'workloads.yml',
                     'workload_config':  'mock_workload_config'
                    },
                    {'id': 'ycsb_load',
                     'type': 'ycsb',
                     'cmd': 'cd YCSB/ycsb-mongodb; ./bin/ycsb load mongodb -s -P ' +
                            'workloads/workloadEvergreen -threads 8; sleep 1;',
                     'config_filename': 'workloadEvergreen',
                     'workload_config': 'mock_workload_config'}
                ],
                'mc': {
                    'monitor_interval': 10,
                    'per_thread_stats': 1
                },
                'post_test': [
                    {'on_workload_client': {
                        'retrieve_files': {
                            'workloads/workload_timestamps.csv': '../workloads_timestamps.csv'}
                        }
                    }
                ]
            }
        } # yapf: disable

    @patch('os.walk')
    @patch('run_test.extract_hosts')
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
        mock_hosts.return_value = [host.HostInfo('10.0.0.0', 'mongod', 0)]

        copy_timeseries(self.config)
        self.assertFalse(mock_copyfile.called)

        mock_walk.reset_mock()
        mock_hosts.reset_mock()
        mock_copyfile.reset_mock()
        mock_walk.return_value = [
            ('/dirpath', ('dirnames', ), ('baz', )),
        ]
        mock_hosts.return_value = [host.HostInfo('10.0.0.0', 'mongod', 0)]

        copy_timeseries(self.config)
        self.assertFalse(mock_copyfile.called)

        mock_walk.reset_mock()
        mock_hosts.reset_mock()
        mock_copyfile.reset_mock()
        mock_walk.return_value = [
            ('/dirpath', ('dirnames', ), ('10.0.0.0--notmatching', )),
            ('/foo/bar', (), ('spam', 'eggs')),
        ]
        mock_hosts.return_value = [host.HostInfo('10.0.0.0', 'mongod', 0)]

        copy_timeseries(self.config)
        self.assertFalse(mock_copyfile.called)

        mock_walk.reset_mock()
        mock_hosts.reset_mock()
        mock_copyfile.reset_mock()
        mock_walk.return_value = [
            ('/dirpath', ('dirnames', ), ('matching--10.0.0.0', )),
        ]
        mock_hosts.return_value = [host.HostInfo('10.0.0.0', 'mongod', 0)]

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
        mock_hosts.return_value = [
            host.HostInfo('10.0.0.0', 'mongod', 0),
            host.HostInfo('10.0.0.1', 'mongod', 1)
        ]

        copy_timeseries(self.config)
        self.assertTrue(mock_copyfile.called)
        self.assertTrue(
            mock_copyfile.called_with('/dirpath0/file0--10.0.0.0',
                                      'reports/mongod.0/matching-dirpath0'))
        self.assertTrue(
            mock_copyfile.called_with('/dirpath1/file1--10.0.0.1',
                                      'reports/mongod.1/matching-dirpath1'))

    @patch('run_test.run_host_command')
    def test_run_pre_post(self, mock_run_host_command):
        """Test run_test.run_pre_post_commands()"""
        command_dicts = [self.config['test_control'], self.config['mongodb_setup']]
        run_pre_post_commands('post_test', command_dicts, self.config, EXCEPTION_BEHAVIOR.EXIT)

        expected_args = ['on_workload_client', 'on_all_servers', 'on_mongod', 'on_configsvr']
        observed_args = []
        for args in mock_run_host_command.call_args_list:
            observed_args.append(args[0][0])
        self.assertEquals(observed_args, expected_args)

    @patch('types.FrameType')
    def test_print_trace_mock_exception(self, mock_frame):
        """ Test run_test.print_trace with mock frame and mock exception"""
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
    @patch('common.host.extract_hosts', return_value=(-1, -1))
    def help_trace_function(self, mock_function, mock_command_dicts, mock_extract_hosts, mock_ssh):
        """
        Test run_test.print_trace by calling run_pre_post_commands with a 'pre_task' key, with a
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
            }
        }
        with LogCapture(level=logging.ERROR) as log_capture:
            # LogCapture captures all log output into the object log_capture. level specifies which
            # log level to detect. logging.ERROR will cause log_capture to only contain logs
            # outputted with the ERROR level or higher. The patch on common.host.make_host mocks
            # the function and is called within run_commands:
            # (pre_task -> dispatch_commands -> run_host_command -> make_host)
            # The mock_function.side_effect causes it to raise an Exception causing print_trace
            # to log the proper information. mock_function will be called within run_command or
            # _run_host_command_map depending on mock_command_dicts. run_pre_post_commands exits
            # with code 1 on exception when given EXCEPTION_BEHAVIOR.EXIT, so self.assertRaises()
            # catches this. The asserts check if the mock_function, extract_hosts, and make_host
            # were called along with asserting the error code was 1.
            return_value = host.RemoteHost(None, None, None)
            with patch('common.host.make_host', return_value=return_value) as mock_make_host:
                mock_function.side_effect = Exception("Mock Exception")
                with self.assertRaises(SystemExit) as exception:
                    run_pre_post_commands('pre_task', mock_command_dicts, mock_config,
                                          EXCEPTION_BEHAVIOR.EXIT)
                self.assertTrue(mock_function.called)
                self.assertTrue(mock_extract_hosts.called)
                self.assertTrue(mock_make_host.called)
                self.assertTrue(mock_ssh.called)
                self.assertEqual(exception.exception.code, 1)
        task = mock_command_dicts[0]['pre_task'][0].iterkeys().next()
        command = mock_command_dicts[0]['pre_task'][0][task]
        error_regex_str = "Exception originated in: .+"
        error_regex_str = error_regex_str + "\nException msg: Mock "
        error_regex_str = error_regex_str + "Exception\nrun_pre_post_commands:\n    "
        error_regex_str = error_regex_str + "in task: " + task + "\n        "
        error_regex_str = error_regex_str + "in command: " + str(command)
        error_pattern = re.compile(error_regex_str)
        list_errors = list(log_capture.actual())  # Get actual string held by loc_capture object
        self.assertRegexpMatches(list_errors[0][2], error_pattern)

    # pylint: disable=no-value-for-parameter
    # pylint is confused by the patch decorator on help_test_trace_function()
    @patch('host.RemoteHost.upload_file')
    def test_print_trace_upload_file(self, mock_upload_file):
        """ Test run_test.print_trace with exception in upload_file"""
        mock_command_dicts = [{
            'pre_task': [{
                'on_workload_client': {
                    'upload_files': {
                        'workloads.tar.gz': 'workloads.tar.gz'
                    }
                }
            }]
        }, {}]
        self.help_trace_function(mock_upload_file, mock_command_dicts)

    @patch('os.path')
    @patch('host.RemoteHost.retrieve_path')
    def test_print_trace_retrieve_path(self, mock_retrieve_path, mock_path):
        """ Test run_test.print_trace with exception in retrieve_path"""
        mock_path.return_value.join.return_value = ""
        mock_path.return_value.normpath.return_value = ""
        mock_command_dicts = [{
            'pre_task': [{
                'on_workload_client': {
                    'retrieve_files': {
                        'workloads.tar.gz': 'workloads.tar.gz'
                    }
                }
            }]
        }, {}]
        self.help_trace_function(mock_retrieve_path, mock_command_dicts)

    @patch('host.RemoteHost.create_file')
    def test_print_trace_create_file(self, mock_create_file):
        """ Test run_test.print_trace with exception in create_file"""
        mock_command_dicts = [{
            'pre_task': [{
                'on_workload_client': {
                    'exec_mongo_shell': {
                        'script': 'mock script'
                    }
                }
            }]
        }, {}]
        self.help_trace_function(mock_create_file, mock_command_dicts)

    # pylint: disable=no-self-use
    @patch("host.RemoteHost")
    @patch("os.makedirs")
    def test_background_command_run(self, mock_makedirs, mock_host):
        """ Test BackgroundCommand run"""
        subject = BackgroundCommand(mock_host, 'command', 'dirname/basename')

        with patch('bin.run_test.open', mock_open()) as mock_file:
            mock_out = mock_file.return_value
            subject.run()
            mock_file.assert_called_with('dirname/basename', 'wb+', 0)
            mock_makedirs.assert_called_with('dirname')
            mock_host.exec_command.assert_called_with(
                'command', out=mock_out, err=mock_out, pty=True)

    # pylint: disable=no-self-use
    @patch("host.RemoteHost")
    def test_background_command_stop(self, mock_host):
        """ Test BackgroundCommand  stop"""
        subject = BackgroundCommand(mock_host, 'command', 'dirname/basename')
        subject.stop()
        mock_host.close.assert_called_once()

    # pylint: disable=unused-argument
    @patch('bin.run_test.make_host')
    @patch('bin.run_test.extract_hosts')
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

        with patch('bin.run_test.BackgroundCommand'):
            command_dict = config['test_control']['run'][1]
            self.assertEqual(start_background_tasks(config, command_dict, test_id), [])

        with patch('bin.run_test.BackgroundCommand'):
            command_dict = config['test_control']['run'][0]
            mock_make_host.return_value = Mock()
            result = start_background_tasks(config, command_dict, test_id)
            self.assertEqual(len(result), 3)

    # pylint: enable=no-value-for-parameter

    @patch('run_test.config_test_control.generate_mc_json')
    @patch('run_test.subprocess.check_call')
    @patch('run_test.copy_perf_output')
    @patch('run_test.run_pre_post_commands')
    def test_run_tests(self, mock_pre_post, mock_copy_perf, mock_mc, mock_mc_json):
        """Test run_tests (the top level workhorse for test_control)"""
        run_tests(self.config)

        # We will check that the calls to run_pre_post_commands() happened in expected order
        expected_args = [
            'pre_task', 'pre_test', 'post_test', 'between_tests', 'pre_test', 'post_test',
            'post_task'
        ]
        observed_args = []
        for args in mock_pre_post.call_args_list:
            observed_args.append(args[0][0])
        self.assertEqual(expected_args, observed_args)

        # These are just throwaway mocks, pylint wants me to do something with them
        mock_copy_perf.assert_called()
        mock_mc.assert_called()
        mock_mc_json.assert_called()


if __name__ == '__main__':
    unittest.main()
