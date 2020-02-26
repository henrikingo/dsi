"""Test workload_setup module"""

from __future__ import absolute_import
import copy
import unittest

from mock import MagicMock, call, patch
import mock

from .. import workload_setup

BASIC_CONFIG = {
    "test_control": {"run": [{"id": x, "type": x} for x in ["foo", "bar"]]},
    "workload_setup": {
        "foo": [
            {"on_localhost": {"exec": "kill -9 python"}},
            {"on_workload_client": {"exec": "kill -9 python"}},
        ],
        "bar": [{"on_workload_client": {"upload_files": {"src": "dest"}}}],
        "baz": [{"something_bad": {"we'll": "never get here"}}],
    },
}


def new_runner(conf):
    """:return configured WorkloadSetupRunner"""
    return workload_setup.WorkloadSetupRunner(conf)


class TestWorkloadSetup(unittest.TestCase):
    """Test workload_setup module"""

    def setUp(self):
        self.config = copy.deepcopy(BASIC_CONFIG)
        self.mock_run_host = MagicMock()

    @patch("bin.workload_setup.host_utils.setup_ssh_agent")
    def test_ignore_done_check(self, mock_setup_ssh_agent):
        """We don't check for done-ness unless told to"""
        runner = new_runner(
            {
                "test_control": {"run": [{"id": "x", "type": "x"}]},
                "workload_setup": {"x": [{"foo": "bar"}]},
            }
        )
        with mock.patch("bin.common.command_runner.run_host_command", self.mock_run_host):
            runner.setup_workloads()
            self.mock_run_host.assert_called_once()
            mock_setup_ssh_agent.assert_called()

    @patch("bin.workload_setup.host_utils.setup_ssh_agent")
    def test_runs_two_types(self, mock_setup_ssh_agent):
        """Two distinct test types"""
        runner = new_runner(self.config)

        # this feels kinda icky...
        # we call all of main which modifies config before we assert mock interactions,
        # and mock interactions aren't call-by-value.
        expected_call_config = copy.deepcopy(BASIC_CONFIG)

        with mock.patch("bin.common.command_runner.run_host_command", self.mock_run_host):
            # run the thing
            runner.setup_workloads()

            expected_calls = [
                call(
                    "on_localhost",
                    self.config["workload_setup"]["foo"][0]["on_localhost"],
                    expected_call_config,
                    "workload_setup",
                ),
                call(
                    "on_workload_client",
                    self.config["workload_setup"]["foo"][1]["on_workload_client"],
                    expected_call_config,
                    "workload_setup",
                ),
                call(
                    "on_workload_client",
                    self.config["workload_setup"]["bar"][0]["on_workload_client"],
                    expected_call_config,
                    "workload_setup",
                ),
            ]
            self.mock_run_host.assert_has_calls(expected_calls)
            mock_setup_ssh_agent.assert_called()
