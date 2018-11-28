import unittest

import grpc._channel as grpc_channel  # pylint: disable=protected-access
from mock import patch, MagicMock, Mock, ANY

import common.host_utils
import common.remote_jasper_host
from test_lib.comparator_utils import ANY_IN_STRING


class RemoteJasperHostTestCase(unittest.TestCase):
    @patch('paramiko.SSHClient')
    def error_handling_helper(self, command, *args, **kwargs):
        """Test errors are correctly logged in RemoteJasperHost.exec_command"""
        host = common.remote_jasper_host.RemoteJasperHost('test_host', 'test_user', 'test_pem_file')

        mock_logger = MagicMock(name='LOG')
        common.remote_jasper_host.LOG.warning = mock_logger

        host._do_exec_command = MagicMock(name='_do_exec_command')

        host.exec_command(command, **kwargs)

        mock_logger.assert_called_once_with(ANY_IN_STRING('is not supported'))

    def test_exec_command_helper(self):
        """Sanity check that error_handling_helper does indeed assert"""
        with self.assertRaises(AssertionError):
            self.error_handling_helper(['dummy_cmd'])

    def test_exec_command_output_timeout_ms(self):
        """Test unsupported parameter"""
        self.error_handling_helper(
            ['dummy_cmd'],
            no_output_timeout_ms=0,
        )

    def test_exec_command_max_time_ms(self):
        """Test unsupported parameter"""
        self.error_handling_helper(
            ['dummy_cmd'],
            max_time_ms=1,
        )

    def test_exec_command_get_pty(self):
        """Test unsupported parameter"""
        self.error_handling_helper(
            ['dummy_cmd'],
            get_pty=1,
        )

    def test_exec_command_stdout(self):
        """Test unsupported parameter"""
        self.error_handling_helper(
            ['dummy_cmd'],
            stdout=1,
        )

    def test_exec_command_stderr(self):
        """Test unsupported parameter"""
        self.error_handling_helper(
            ['dummy_cmd'],
            stderr=1,
        )

    @patch('paramiko.SSHClient')
    def remote_jasper_host_mocked_grpc(self, mock_ssh):
        _ = mock_ssh
        host = common.remote_jasper_host.RemoteJasperHost('test_host', 'test_user', 'test_pem_file')

        host.stub = MagicMock(name='stub')

        host.jasper_pb = MagicMock(name='jasper_pb')
        host.jasper_grpc = MagicMock(name='jasper_grpc')

        return host

    def test_do_exec_command_fail(self):
        mock_logger = MagicMock(name='LOG')

        host = self.remote_jasper_host_mocked_grpc()

        mock_wait = Mock(name='stub_wait_return_value')
        mock_wait.exit_code = 1
        mock_wait.success = False

        host.stub.Wait.return_value = mock_wait

        exit_code = host._do_exec_command(['dummy_cmd'], mock_logger)

        self.assertEqual(exit_code, 1)
        mock_logger.error.assert_called_once_with(ANY_IN_STRING('Failed to wait'), ANY, ANY, ANY)

    def test_do_exec_command_success(self):
        mock_logger = MagicMock(name='LOG')

        host = self.remote_jasper_host_mocked_grpc()

        mock_wait = Mock(name='stub_wait_return_value')
        mock_wait.exit_code = 0

        host.stub.Wait.return_value = mock_wait

        exit_code = host._do_exec_command(['dummy_cmd'], mock_logger)

        self.assertEqual(exit_code, 0)
        mock_logger.error.assert_not_called()

    def test_do_exec_command_swallow_error_from_wait(self):
        mock_logger = MagicMock(name='LOG')

        host = self.remote_jasper_host_mocked_grpc()

        mock_error = grpc_channel._Rendezvous(MagicMock(), MagicMock(), MagicMock(), MagicMock())
        mock_wait = Mock(name='stub_wait_return_value')
        mock_wait.side_effect = mock_error  # pylint: disable=protected-access

        host.stub.Wait = mock_wait

        exit_code = host._do_exec_command(['dummy_cmd'], mock_logger)

        self.assertEqual(exit_code, 0)

        mock_logger.error.assert_called_once()

    def test_do_exec_command_unexpected_error(self):
        mock_logger = MagicMock(name='LOG')

        host = self.remote_jasper_host_mocked_grpc()

        mock_create = Mock(name='stub_wait_return_value')
        mock_create.side_effect = AssertionError

        host.stub.Create = mock_create

        with self.assertRaises(AssertionError):
            # Simulate gRPC throwing errors if it fails to connect to the host.
            host._do_exec_command(['dummy_cmd'], mock_logger)


if __name__ == '__main__':
    unittest.main()
