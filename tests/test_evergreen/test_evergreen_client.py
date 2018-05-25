"""Unit tests for evergreen.evergreen_client."""
import copy
import unittest

from mock import patch

from evergreen import evergreen_client


class TestEvergreenClient(unittest.TestCase):
    """Tests are related to Evergreen API access"""

    def setUp(self):
        """Get evergreen credentials from config file."""
        self.mock_evg_history = copy.deepcopy(MOCK_EVG_HISTORY)

    @patch('evergreen.evergreen_client.Client.query_project_history')
    def test_get_all_tasks(self, mock_query_history):
        expected = [{'task': 'compile', 'variant': 'compile-rhel70'},
                    {'task': 'compile_wtdevelop', 'variant': 'compile-rhel70'},
                    {'task': 'bestbuy_agg_WT', 'variant': 'linux-1-node-replSet'},
                    {'task': 'crud_workloads_MMAPv1', 'variant': 'linux-1-node-replSet'},
                    {'task': 'crud_workloads_WT', 'variant': 'linux-1-node-replSet'},
                    {'task': 'bestbuy_agg_MMAPv1', 'variant': 'linux-1-node-replSet'}]  #  yapf: disable

        mock_query_history.return_value = self.mock_evg_history

        evg_client = evergreen_client.Client()
        result = evg_client.get_all_tasks('sys-perf')
        self.assertEqual(result, expected)

    @patch('evergreen.evergreen_client.helpers.get_as_json')
    @patch('evergreen.evergreen_client.Client.query_project_history')
    def test_find_perf_tag(self, mock_query_history, mock_get):
        expected = '5af2dc5be3c33109e3d56482'
        mock_query_history.return_value = self.mock_evg_history
        mock_get.return_value = {'version_id': '5af2dc5be3c33109e3d56482'}

        evg_client = evergreen_client.Client()
        result = evg_client.find_perf_tag('sys-perf', '3.4.14-Baseline')
        self.assertEqual(result, expected)


# pylint: disable=line-too-long
MOCK_EVG_HISTORY = {
    "project": "sys-perf",
    "versions": [{
        "version_id": "sys_perf_d0fa6b7523864f5f96262731c29d866913bc7462",
        "author": "Daniel Gottlieb",
        "revision": "d0fa6b7523864f5f96262731c29d866913bc7462",
        "message": "SERVER-35128: Add a boost::optional overload to Logstream builder's operator<<",
        "builds": {
            "compile-rhel70": {
                "build_id": "sys_perf_compile_rhel70_d0fa6b7523864f5f96262731c29d866913bc7462_18_05_24_13_56_09",
                "name": "Compile on rhel70",
                "tasks": {
                    "compile": {
                        "task_id": "sys_perf_compile_rhel70_compile_d0fa6b7523864f5f96262731c29d866913bc7462_18_05_24_13_56_09",
                        "status": "undispatched",
                        "time_taken": 0
                    },
                    "compile_wtdevelop": {
                        "task_id": "sys_perf_compile_rhel70_compile_wtdevelop_d0fa6b7523864f5f96262731c29d866913bc7462_18_05_24_13_56_09",
                        "status": "undispatched",
                        "time_taken": 0
                    }
                }
            },
            "linux-1-node-replSet": {
                "build_id": "sys_perf_linux_1_node_replSet_d0fa6b7523864f5f96262731c29d866913bc7462_18_05_24_13_56_09",
                "name": "Linux 1-Node ReplSet",
                "tasks": {
                    "bestbuy_agg_MMAPv1": {
                        "task_id": "sys_perf_linux_1_node_replSet_bestbuy_agg_MMAPv1_d0fa6b7523864f5f96262731c29d866913bc7462_18_05_24_13_56_09",
                        "status": "undispatched",
                        "time_taken": 0
                    },
                    "bestbuy_agg_WT": {
                        "task_id": "sys_perf_linux_1_node_replSet_bestbuy_agg_WT_d0fa6b7523864f5f96262731c29d866913bc7462_18_05_24_13_56_09",
                        "status": "undispatched",
                        "time_taken": 0
                    },
                    "crud_workloads_MMAPv1": {
                        "task_id": "sys_perf_linux_1_node_replSet_crud_workloads_MMAPv1_d0fa6b7523864f5f96262731c29d866913bc7462_18_05_24_13_56_09",
                        "status": "undispatched",
                        "time_taken": 0
                    },
                    "crud_workloads_WT": {
                        "task_id": "sys_perf_linux_1_node_replSet_crud_workloads_WT_d0fa6b7523864f5f96262731c29d866913bc7462_18_05_24_13_56_09",
                        "status": "undispatched",
                        "time_taken": 0
                    }
                }
            }
        }
    }]
}  #  yapf: disable
