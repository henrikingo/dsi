#!/usr/bin/env python
"""Test workload_setup module"""

import copy
import unittest

from mock import MagicMock, mock

import workload_setup

BASIC_CONFIG = {
    'test_control': {
        'run': [{
            'id': x,
            'type': x
        } for x in ['foo', 'bar']]
    },
    'workload_setup': {
        'foo': [{
            'on_localhost': {
                'exec': 'kill -9 python'
            }
        }, {
            'on_workload_client': {
                'exec': 'kill -9 python'
            }
        }],
        'bar': [{
            'on_workload_client': {
                'upload_files': {
                    'src': 'dest'
                }
            }
        }],
        'baz': [{
            'something_bad': {
                "we'll": "never get here"
            }
        }]
    }
}


class TestWorkloadSetup(unittest.TestCase):
    """Test workload_setup module"""
    def setUp(self):
        self.config = copy.deepcopy(BASIC_CONFIG)
        self.mock_run_host = MagicMock()

    def test_ignore_done_check(self):
        """We don't check for done-ness unless told to"""
        runner = workload_setup.WorkloadSetupRunner({
            'test_control': {
                'run': [{
                    'id': 'x',
                    'type': 'x'
                }]
            },
            'workload_setup': {
                'x': [{
                    'foo': 'bar'
                }]
            }
        })
        with mock.patch('common.command_runner.run_host_command', self.mock_run_host):
            runner.setup_workloads()
            self.mock_run_host.assert_called_once()

    def test_runs_two_types(self):
        """Two distinct test types"""
        runner = workload_setup.WorkloadSetupRunner(self.config)
        with mock.patch('common.command_runner.run_host_command', self.mock_run_host):
            # run the thing
            runner.setup_workloads()
            self.assertEqual(3, self.mock_run_host.call_count)
