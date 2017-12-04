''' Test config_test_control.py '''

import glob
import json
import os
import unittest
import shutil
import sys

import yaml

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config_test_control  #pylint: disable=wrong-import-position


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
        self.config_file = 'test_control.yml'
        self.copied_files = []  # List of files copied
        for filename in glob.glob(os.path.join(self.artifact_dir, '*.yml')):
            shutil.copy(filename, '.')
            self.copied_files.append(os.path.basename(filename))

    def tearDown(self):
        ''' Delete temporary files from run '''
        files = os.listdir('.')
        for filename in files:
            if filename.startswith("mc_.json"):
                os.remove(filename)
        os.remove('test_control.yml')
        for filename in self.copied_files:
            os.remove(filename)
        if os.path.isfile('workloads.yml'):
            os.remove('workloads.yml')

    def test_benchrun(self):
        '''
        Load in configuration for a single cluster with benchrun
        tests. Check the generated mc.json and workloads.yml
        '''
        shutil.copy('test_control.benchRun.yml', self.config_file)
        config_test_control.generate_mc_json()

        self.assertEqual(
            load_json('mc_benchRun-wiredTiger.json'),
            load_json('mc.benchrun.json.ok', self.artifact_dir),
            'mc.json doesn\'t match expected for test_control.benchRun.yml')
        self.assertEqual(
            load_yaml('workloads.yml'), load_yaml('workloads.benchrun.yml.ok', self.artifact_dir),
            'workloads.yml doesn\'t match expected for test_control.benchRun.yml')

    # Check only the first ycsb test for now. Not adding in all of the tests because we are
    # removing mc momentarily.
    def test_ycsb(self):
        '''
        Load in the configuration for a single cluster with ycsb
        tests. Check the generated mc.json

        '''
        shutil.copy('test_control.ycsb.yml', self.config_file)
        config_test_control.generate_mc_json(test_index=0)
        self.assertEqual(
            load_json('mc_ycsb_load-wiredTiger.json'),
            load_json('mc.ycsb.json.ok', self.artifact_dir),
            'mc.json doesn\'t match expected for test_control.ycsb.yml')


if __name__ == '__main__':
    unittest.main()
