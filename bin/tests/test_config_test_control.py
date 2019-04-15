''' Test config_test_control.py '''

import logging
import os
import unittest

from mock import Mock, patch
from testfixtures import LogCapture

import test_control

from common.config import ConfigDict
from common.remote_host import RemoteHost
from test_lib.fixture_files import FixtureFiles

FIXTURE_FILES = FixtureFiles(dir_name=os.path.dirname(__file__), subdir_name='config_test_control')


class TestConfigTestControl(unittest.TestCase):
    ''' Test config_test_control.py'''

    def setUp(self):
        """
        Setup basic environment
        """
        # Mocking `ConfigDict.assert_valid_ids` because it enforces structural constraints on yaml
        # files that aren't necessary here.
        with patch('common.config.ConfigDict.assert_valid_ids') as mock_assert_valid_ids:
            prev_dir = os.getcwd()
            os.chdir(FIXTURE_FILES.fixture_dir_path)
            self.config = ConfigDict('test_control')
            self.config.load()
            mock_assert_valid_ids.assert_called_once()
            os.chdir(prev_dir)

    def test_benchrun_workload_config(self):
        """
        Test that generate_config_files works with a benchrun workload
        """
        test = self.config['test_control']['run'][0]
        mock_host = Mock(spec=RemoteHost)
        test_control.generate_config_file(test, FIXTURE_FILES.fixture_dir_path, mock_host)
        self.assertEqual(
            FIXTURE_FILES.load_yaml_file('workloads.yml'),
            FIXTURE_FILES.load_yaml_file('workloads.benchrun.yml.ok'),
            'workloads.yml doesn\'t match expected for test_control.yml')
        mock_host.upload_file.assert_called_once_with(
            FIXTURE_FILES.fixture_file_path(test['config_filename']), test['config_filename'])

    def test_ycsb_workload_config(self):
        """
        Test that generate_config_files works with a ycsb run
        """
        test = self.config['test_control']['run'][1]
        mock_host = Mock(spec=RemoteHost)
        test_control.generate_config_file(test, FIXTURE_FILES.fixture_dir_path, mock_host)
        self.assertEqual(
            FIXTURE_FILES.load_yaml_file('workloadEvergreen'),
            FIXTURE_FILES.load_yaml_file('workloadEvergreen.ok'),
            'workloadEvergreen doesn\'t match expected for test_control.yml')
        mock_host.upload_file.assert_called_once_with(
            FIXTURE_FILES.fixture_file_path(test['config_filename']), test['config_filename'])

    @patch('test_control.open')
    def test_generate_config_no_config(self, mock_open):
        """
        Test that generate_config_file doesn't create a workload file and logs the correct message
        if there is no config file
        """
        test = self.config['test_control']['run'][2]
        mock_host = Mock(spec=RemoteHost)
        with LogCapture(level=logging.WARNING) as warning:
            test_control.generate_config_file(test, FIXTURE_FILES.fixture_dir_path, mock_host)
        warning.check(('test_control', 'WARNING', 'No workload config in test control'))
        mock_open.assert_not_called()
        mock_host.upload_file.assert_not_called()


if __name__ == '__main__':
    unittest.main()
