''' Test config_test_control.py '''

import glob
import json
import logging
import os
import unittest
import shutil

from mock import Mock, patch
from testfixtures import LogCapture
import yaml

from common.config import ConfigDict
from common.remote_host import RemoteHost
import test_control


def load_json(filename, directory=None):
    ''' Convenience method to read in a json file '''
    if not directory:
        directory = '.'
    with open(os.path.join(directory, filename)) as json_file:
        return json.load(json_file)


def load_yaml(filename, directory=None):
    ''' Convenience method to read in a yaml file '''
    if not directory:
        directory = '.'
    with open(os.path.join(directory, filename)) as yaml_file:
        return yaml.load(yaml_file)


class TestConfigTestControl(unittest.TestCase):
    ''' Test config_test_control.py'''

    def setUp(self):
        """
        Setup basic environment
        """
        self.test_dir = os.path.dirname(os.path.abspath(__file__))
        self.artifact_dir = os.path.join(self.test_dir, 'config_test_control')
        self.repo_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.copied_files = []  # List of files copied
        for filename in glob.glob(os.path.join(self.artifact_dir, '*.yml')):
            shutil.copy(filename, '.')
            self.copied_files.append(os.path.basename(filename))
        self.config = ConfigDict('test_control')
        self.config.load()

    def tearDown(self):
        """
        Delete temporary files from run
        """
        for filename in self.copied_files:
            os.remove(filename)
        if os.path.isfile('workloads.yml'):
            os.remove('workloads.yml')
        if os.path.isfile('workloadEvergreen'):
            os.remove('workloadEvergreen')

    def test_benchrun_workload_config(self):
        """
        Test that generate_config_files works with a benchrun workload
        """
        test = self.config['test_control']['run'][0]
        mock_host = Mock(spec=RemoteHost)
        test_control.generate_config_file(test, '.', mock_host)
        self.assertEqual(
            load_yaml('workloads.yml'), load_yaml('workloads.benchrun.yml.ok', self.artifact_dir),
            'workloads.yml doesn\'t match expected for test_control.yml')
        mock_host.upload_file.assert_called_once_with(
            os.path.join('.', test['config_filename']), test['config_filename'])

    def test_ycsb_workload_config(self):
        """
        Test that generate_config_files works with a ycsb run
        """
        test = self.config['test_control']['run'][1]
        mock_host = Mock(spec=RemoteHost)
        test_control.generate_config_file(test, '.', mock_host)
        self.assertEqual(
            load_yaml('workloadEvergreen'), load_yaml('workloadEvergreen.ok', self.artifact_dir),
            'workloadEvergreen doesn\'t match expected for test_control.yml')
        mock_host.upload_file.assert_called_once_with(
            os.path.join('.', test['config_filename']), test['config_filename'])

    @patch('test_control.open')
    def test_generate_config_no_config(self, mock_open):
        """
        Test that generate_config_file doesn't create a workload file and logs the correct message
        if there is no config file
        """
        test = self.config['test_control']['run'][2]
        mock_host = Mock(spec=RemoteHost)
        with LogCapture(level=logging.WARNING) as warning:
            test_control.generate_config_file(test, '.', mock_host)
        warning.check(('test_control', 'WARNING', 'No workload config in test control'))
        mock_open.assert_not_called()
        mock_host.upload_file.assert_not_called()


if __name__ == '__main__':
    unittest.main()
