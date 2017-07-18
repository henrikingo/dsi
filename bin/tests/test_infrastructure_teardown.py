"""
Unit test for infrastructure_provisioning.py
"""

import unittest
from mock import patch, call

from infrastructure_teardown import destroy_resources

class TestInfrastructureTeardown(unittest.TestCase):
    """ Test suite for infrastructure_teardown.py """

    def setUp(self):
        self.os_environ = {
            'TERRAFORM': 'test/path/terraform'
        }

    @patch('infrastructure_teardown.subprocess.check_call')
    @patch('infrastructure_teardown.glob.glob')
    @patch('infrastructure_teardown.os')
    def test_destroy_resources(self, mock_os, mock_glob, mock_check_call):
        """ Test infrastructure_teardown.destroy_resources """
        mock_os.path.dirname.return_value = 'teardown/script/path'
        mock_os.environ.__getitem__.side_effect = self.os_environ.__getitem__
        mock_os.environ.__contains__.side_effect = self.os_environ.__contains__
        mock_os.getcwd.return_value = 'previous/directory'
        mock_os.path.isfile.return_value = True
        mock_glob.return_value = True
        destroy_resources()
        mock_glob.assert_called_with('teardown/script/path/provisioned.*')
        chdir_calls = [call('teardown/script/path'),
                       call('previous/directory')]
        mock_os.chdir.assert_has_calls(chdir_calls)
        mock_os.path.isfile.assert_called_with('cluster.json')
        mock_check_call.assert_called_with([self.os_environ['TERRAFORM'],
                                            'destroy',
                                            '-var-file=cluster.json',
                                            '-force'])


if __name__ == '__main__':
    unittest.main()
