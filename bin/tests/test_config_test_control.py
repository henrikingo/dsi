''' Test config_test_control.py '''

import glob
import json
import logging
import os
import unittest
import shutil

from mock import patch
from testfixtures import LogCapture
import yaml

from common.config import ConfigDict
import run_test  #pylint: disable=wrong-import-position


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
        ''' Setup basic environment '''
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
        ''' Delete temporary files from run '''
        for filename in self.copied_files:
            os.remove(filename)
        if os.path.isfile('workloads.yml'):
            os.remove('workloads.yml')
        if os.path.isfile('workloadEvergreen'):
            os.remove('workloadEvergreen')

    def test_benchrun_workload_config(self):
        '''
        Test that generate_config_files works with a benchrun workload
        '''
        run_test.generate_config_file(self.config['test_control']['run'][0])
        self.assertEqual(
            load_yaml('workloads.yml'), load_yaml('workloads.benchrun.yml.ok', self.artifact_dir),
            'workloads.yml doesn\'t match expected for test_control.yml')

    def test_ycsb_workload_config(self):
        ''' Test that generate_config_files works with a ycsb run
        '''
        run_test.generate_config_file(self.config['test_control']['run'][1])
        self.assertEqual(
            load_yaml('workloadEvergreen'), load_yaml('workloadEvergreen.ok', self.artifact_dir),
            'workloadEvergreen doesn\'t match expected for test_control.yml')

    @patch('run_test.open')
    def test_generate_config_no_config(self, mock_open):
        '''Test that generate_config_file doesn't create a workload file and logs the correct
        message if there is no config file'''
        with LogCapture(level=logging.WARNING) as warning:
            run_test.generate_config_file(self.config['test_control']['run'][2])
        warning.check(('run_test', 'WARNING', 'No workload config in test control'))
        mock_open.assert_not_called()


if __name__ == '__main__':
    unittest.main()
