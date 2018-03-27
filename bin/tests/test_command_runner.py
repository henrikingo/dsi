"""Tests for bin/common/command_runner.py"""

import unittest
import shutil
import os

from mock import patch, Mock, mock

import common.command_runner
from common.config import ConfigDict

# Useful absolute directory paths.
FIXTURE_DIR_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "unittest-files")


def fixture_file_path(file_path):
    """Return the absolute path of a file at `file_path` inside the fixture files directory."""

    return os.path.join(FIXTURE_DIR_PATH, file_path)


class CommandRunnerTestCase(unittest.TestCase):
    """ Unit Tests for Host Utils library """

    def _delete_fixtures(self):
        """ delete fixture path and set filename attribute """
        local_host_path = fixture_file_path('fixtures')
        self.filename = os.path.join(local_host_path, 'file')
        shutil.rmtree(os.path.dirname(self.filename), ignore_errors=True)

    def setUp(self):
        """ Init a ConfigDict object and load the configuration files from docs/config-specs/ """
        self.old_dir = os.getcwd()  # Save the old path to restore
        # Note that this chdir only works without breaking relative imports
        # because it's at the same directory depth
        os.chdir(os.path.dirname(os.path.abspath(__file__)) + '/../../docs/config-specs/')
        self.config = ConfigDict('mongodb_setup')
        self.config.load()
        self.parent_dir = os.path.join(os.path.expanduser('~'), 'checkout_repos_test')

        self._delete_fixtures()

    def tearDown(self):
        """ Restore working directory """
        os.chdir(self.old_dir)

        self._delete_fixtures()

    @patch("common.command_runner._run_host_command_map")
    def test_make_host_runner_str(self, mock_run_host_command_map):
        """ Test run RemoteHost.make_host_runner with str"""
        with patch('common.host_factory.make_host') as mock_make_host:
            mock_target_host = Mock()
            mock_make_host.return_value = mock_target_host
            common.command_runner.make_host_runner("host_info", 'command', "ssh_user",
                                                   "ssh_key_file", "test_id")
            mock_make_host.assert_called_once_with("host_info", "ssh_user", "ssh_key_file", None)
            mock_target_host.run.assert_called_once_with('command')
            mock_target_host.close.assert_called_once()

    @patch("common.command_runner._run_host_command_map")
    def test_make_host_runner_map(self, mock_run_host_command_map):
        """ Test run Remotecommon.command_runner.make_host_runner with map"""

        with patch('common.host_factory.make_host') as mock_make_host:
            command = {}
            mock_target_host = Mock()
            mock_make_host.return_value = mock_target_host
            common.command_runner.make_host_runner("host_info", command, "ssh_user", "ssh_key_file",
                                                   'test_id')
            mock_make_host.assert_called_once_with("host_info", "ssh_user", "ssh_key_file", None)
            mock_run_host_command_map.assert_called_once_with(mock_target_host, command, 'test_id')
            mock_target_host.close.assert_called_once()

    def test_run_host_commands(self):
        """Test 2-commands common.command_runner.run_host_commands invocation"""
        with patch('common.host_factory.RemoteHost') as mongod:
            commands = [
                {
                    'on_workload_client': {
                        'upload_files': [{
                            'source': 'src1',
                            'target': 'dest1'
                        }]
                    }
                },
                {
                    'on_workload_client': {
                        'upload_files': [{
                            'source': 'src2',
                            'target': 'dest2'
                        }]
                    }
                },
            ]
            common.command_runner.run_host_commands(commands, self.config, "test_id")
            assert mongod.call_count == 2

    def test_run_host_command_map(self):
        """ Test run command map not known """

        with self.assertRaises(UserWarning):
            with patch('common.host_factory.RemoteHost') as mongod:
                command = {"garbage": {"remote_path": "mongos.log"}}
                common.command_runner._run_host_command_map(mongod, command, "test_id")

    def __run_host_command_map_ex(self, command, run_return_value=False, exec_return_value=None):
        with patch('common.host_factory.RemoteHost') as mongod:
            if run_return_value is not None:
                mongod.run.return_value = run_return_value
            else:
                mongod.exec_mongo_command.return_value = exec_return_value
            common.command_runner._run_host_command_map(mongod, command, "test_id")

    def test__exec_ex(self):
        """ Test run command map excpetion """

        # test upload_files
        with self.assertRaisesRegexp(common.host_utils.HostException, r'^\(1, .*cowsay moo'):
            command = {"exec": 'cowsay moo'}
            self.__run_host_command_map_ex(command)

    def test__exec_mongo_shell_ex(self):
        """ Test run command map excpetion """

        with self.assertRaisesRegexp(common.host_utils.HostException, r'^\(1, .*this is a script'):
            command = {
                "exec_mongo_shell": {
                    "script": "this is a script",
                    "connection_string": "connection string"
                }
            }
            self.__run_host_command_map_ex(command, run_return_value=None, exec_return_value=1)

    def test_upload_repo_files(self):
        """ Test run command map upload_repo_files """
        root = common.utils.get_dsi_path() + os.sep

        # test upload_repo_files
        with patch('common.host_factory.RemoteHost') as mongod:
            command = {"upload_repo_files": [{"target": "remote_path", "source": "mongos.log"}]}
            common.command_runner._run_host_command_map(mongod, command, "test_id")
            mongod.upload_file.assert_called_once_with(root + "mongos.log", "remote_path")

        with patch('common.host_factory.RemoteHost') as mongod:
            command = {
                "upload_repo_files": [{
                    "target": "remote_path",
                    "source": "mongos.log"
                }, {
                    "target": "to",
                    "source": "from"
                }]
            }
            common.command_runner._run_host_command_map(mongod, command, "test_id")
            calls = [
                mock.call(root + "mongos.log", "remote_path"),
                mock.call(root + "from", "to"),
            ]
            mongod.upload_file.assert_has_calls(calls, any_order=True)

    def test_upload_files(self):
        """ Test run command map upload_files """

        # test upload_files
        with patch('common.host_factory.RemoteHost') as mongod:
            command = {"upload_files": [{"target": "remote_path", "source": "mongos.log"}]}
            common.command_runner._run_host_command_map(mongod, command, "test_id")
            mongod.upload_file.assert_called_once_with("mongos.log", "remote_path")

        with patch('common.host_factory.RemoteHost') as mongod:
            command = {
                "upload_files": [{
                    "source": "mongos.log",
                    "target": "remote_path"
                }, {
                    "source": "to",
                    "target": "from"
                }]
            }
            common.command_runner._run_host_command_map(mongod, command, "test_id")
            calls = [mock.call("mongos.log", "remote_path"), mock.call("to", "from")]
            mongod.upload_file.assert_has_calls(calls, any_order=True)

    def test_retrieve_files(self):
        """ Test run command map retrieve_files """

        # retrieve_files tests
        with patch('common.host_factory.RemoteHost') as mongod:
            mock_retrieve_file = Mock()
            mongod.retrieve_path = mock_retrieve_file

            command = {"retrieve_files": [{"source": "remote_path", "target": "mongos.log"}]}
            mongod.alias = 'host'
            common.command_runner._run_host_command_map(mongod, command, "test_id")
            mock_retrieve_file.assert_any_call("remote_path", "reports/test_id/host/mongos.log")

        # retrieve_files tests
        with patch('common.host_factory.RemoteHost') as mongod:
            mock_retrieve_file = Mock()
            mongod.retrieve_path = mock_retrieve_file

            command = {"retrieve_files": [{"source": "remote_path", "target": "mongos.log"}]}
            mongod.alias = 'host'
            common.command_runner._run_host_command_map(mongod, command, "test_id")
            mock_retrieve_file.assert_any_call("remote_path", "reports/test_id/host/mongos.log")

        with patch('common.host_factory.RemoteHost') as mongod:
            mock_retrieve_file = Mock()
            mongod.retrieve_path = mock_retrieve_file

            command = {"retrieve_files": [{"source": "remote_path", "target": "local_path"}]}
            mongod.alias = 'host'
            common.command_runner._run_host_command_map(mongod, command, "test_id")
            mock_retrieve_file.assert_any_call("remote_path", "reports/test_id/host/local_path")

        with patch('common.host_factory.RemoteHost') as mongod:
            mock_retrieve_file = Mock()
            mongod.retrieve_path = mock_retrieve_file

            mongod.alias = "mongod.0"
            common.command_runner._run_host_command_map(mongod, command, "test_id")
            mock_retrieve_file.assert_any_call("remote_path", "reports/test_id/mongod.0/local_path")

        with patch('common.host_factory.RemoteHost') as mongod:
            mock_retrieve_file = Mock()
            mongod.retrieve_path = mock_retrieve_file

            command = {"retrieve_files": [{"source": "remote_path", "target": "./local_path"}]}
            mongod.alias = "mongos.0"
            common.command_runner._run_host_command_map(mongod, command, "test_id")
            mock_retrieve_file.assert_any_call("remote_path", "reports/test_id/mongos.0/local_path")

    def test_exec(self):
        """ Test run command map exec """

        # test exec
        with patch('common.host_factory.RemoteHost') as mongod:
            command = {"exec": "this is a command"}
            mongod.run.return_value = True
            common.command_runner._run_host_command_map(mongod, command, "test_id")
            mongod.run.assert_called_once_with(["this", "is", "a", "command"])

    def test_exec_mongo_shell(self):
        """ Test run command map exec mongo shell """

        # test exec_mongo_shell
        with patch('common.host_factory.RemoteHost') as mongod:
            command = {
                "exec_mongo_shell": {
                    "script": "this is a script",
                    "connection_string": "connection string"
                }
            }
            mongod.exec_mongo_command.return_value = 0
            common.command_runner._run_host_command_map(mongod, command, "test_id")
            mongod.exec_mongo_command.assert_called_once_with(
                "this is a script", connection_string="connection string")

        with patch('common.host_factory.RemoteHost') as mongod:
            command = {"exec_mongo_shell": {"script": "this is a script"}}
            mongod.exec_mongo_command.return_value = 0
            common.command_runner._run_host_command_map(mongod, command, "test_id")
            mongod.exec_mongo_command.assert_called_once_with(
                "this is a script", connection_string="")


if __name__ == '__main__':
    unittest.main()
