"""
Unit tests for 'bootstrap.py'.
"""
# pylint: disable=invalid-name
# pylint: disable=too-many-public-methods
import copy
import logging
import os
import shutil
import subprocess
import sys
import unittest
import yaml
from mock import patch
from testfixtures import LogCapture

# TODO: Remove all calls to sys.path.append.
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import bootstrap

class TestBootstrap(unittest.TestCase):
    """Test suite for bootstrap.py."""

    def test_read_runtime_values(self):
        """Testing read_runtime_values method does not modify config"""
        master_config = {'test_control': 'benchRun',
                         'ssh_key_file': 'aws_ssh_key.pem',
                         'storageEngine': 'wiredTiger',
                         'aws_secret_key': 'NoSecretKey',
                         'aws_access_key': 'NoAccessKey',
                         'infrastructure_provisioning': 'single',
                         'mongodb_setup': 'standalone',
                         'platform': 'linux',
                         'production': False,
                         'ssh_key_name': 'serverteam-perf-ssh-key',
                         'directory': '.',
                         'mongodb_binary_archive': ""}
        test_config = copy.copy(bootstrap.DEFAULT_CONFIG)
        bootstrap.read_runtime_values(test_config)
        self.assertEqual(test_config, master_config)

    @patch('os.path.expanduser')
    def test_read_aws_creds(self, mock_expanduser):
        """Testing read_aws_creds method correctly modifies config"""
        test_configpath = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), 'test_credentials')
        with open(test_configpath, 'w+') as test_configfile:
            test_configfile.write('[default]\naws_access_key_id = '
                                  'test_aws_access_key\naws_secret_access_key = '
                                  'test_aws_secret_key')
        mock_expanduser.return_value = test_configpath
        master_config = copy.copy(bootstrap.DEFAULT_CONFIG)
        test_config = bootstrap.read_aws_creds(copy.copy(master_config))
        master_config['aws_access_key'] = 'test_aws_access_key'
        master_config['aws_secret_key'] = 'test_aws_secret_key'
        self.assertEqual(test_config, master_config)

        # Removing created file
        os.remove(test_configpath)

    @patch('os.path.expanduser')
    def test_read_aws_creds_and_env_vars(self, mock_expanduser):
        """Testing read_aws_creds and read_env_vars simultaneously"""
        test_configpath = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), 'test_credentials')
        with open(test_configpath, 'w+') as test_configfile:
            test_configfile.write('[default]\naws_access_key_id = '
                                  'test_aws_access_key1\naws_secret_access_key = '
                                  'test_aws_secret_key1')
        mock_expanduser.return_value = test_configpath
        master_config = copy.copy(bootstrap.DEFAULT_CONFIG)
        bootstrap.read_runtime_values(master_config)
        bootstrap.parse_command_line(master_config, [])
        with patch.dict('os.environ',
                        {'AWS_ACCESS_KEY_ID': 'test_aws_access_key2',
                         'AWS_SECRET_ACCESS_KEY': 'test_aws_secret_key2'}):
            test_config = bootstrap.build_config([])
        master_config['aws_access_key'] = 'test_aws_access_key2'
        master_config['aws_secret_key'] = 'test_aws_secret_key2'
        self.assertEqual(test_config, master_config)

        # Removing created file
        os.remove(test_configpath)

    def test_read_env_vars(self):
        """Testing read_env_vars method correctly modifies config"""
        master_config = copy.copy(bootstrap.DEFAULT_CONFIG)
        test_config = copy.copy(bootstrap.DEFAULT_CONFIG)
        with patch.dict('os.environ',
                        {'AWS_ACCESS_KEY_ID': 'test_aws_access_key',
                         'AWS_SECRET_ACCESS_KEY': 'test_aws_secret_key'}):
            test_config = bootstrap.read_env_vars(test_config)
        master_config['aws_access_key'] = 'test_aws_access_key'
        master_config['aws_secret_key'] = 'test_aws_secret_key'
        self.assertEqual(test_config, master_config)

    def test_parse_command_line_no_args(self):
        """Testing for parse_command_line (no args), modifying config"""
        master_config = copy.copy(bootstrap.DEFAULT_CONFIG)
        test_config = copy.copy(bootstrap.DEFAULT_CONFIG)
        test_config = bootstrap.parse_command_line(test_config, [])
        self.assertEquals(test_config, master_config)

    def test_parse_command_line_no_cluster(self):
        """Testing for parse_command_line (1 arg = 'none'), modifying config"""
        args = ['-c' 'none']
        master_config = copy.copy(bootstrap.DEFAULT_CONFIG)
        master_config['infrastructure_provisioning'] = 'none'
        test_config = copy.copy(bootstrap.DEFAULT_CONFIG)
        test_config = bootstrap.parse_command_line(test_config, args)
        self.assertEquals(test_config, master_config)

    def test_parse_command_line_all_args(self):
        """Testing for parse_command_line (all args given), modifying config"""
        args = ['-c', 'test_cluster_type',
                '--directory', 'test_directory',
                '--mc', 'test_mc',
                '--owner', 'test_owner',
                '-p', 'test_ssh_key_file',
                '--ssh-key', 'test_ssh_key_name',
                '--aws-key-name', 'test_aws_access_key',
                '--aws-secret-file', 'test_aws_secret_file',
                '--terraform', 'test_terraform', '--production']

        master_config = copy.copy(bootstrap.DEFAULT_CONFIG)
        master_config['infrastructure_provisioning'] = 'test_cluster_type'
        master_config['owner'] = 'test_owner'
        master_config['aws_access_key'] = 'test_aws_access_key'
        master_config['aws_secret_file'] = 'test_aws_secret_file'
        master_config['ssh_key_file'] = 'test_ssh_key_file'
        master_config['ssh_key_name'] = 'test_ssh_key_name'
        master_config['directory'] = 'test_directory'
        master_config['production'] = True
        master_config['mc'] = 'test_mc'
        master_config['terraform'] = 'test_terraform'

        test_config = copy.copy(bootstrap.DEFAULT_CONFIG)
        test_config = bootstrap.parse_command_line(test_config, args)

        self.assertEquals(test_config, master_config)

    def test_parse_command_line_all_args_alternate(self):
        """Testing for parse_command_line (all alt cmds), modifying config"""
        args = ['--cluster-type', 'test_cluster_type',
                '--directory', 'test_directory',
                '--mc', 'test_mc',
                '--owner', 'test_owner',
                '--ssh-keyfile-path', 'test_ssh_key_file',
                '--ssh-key-name', 'test_ssh_key_name',
                '--aws-access-key', 'test_aws_access_key',
                '--aws-secret-file', 'test_aws_secret_file',
                '--terraform', 'test_terraform', '--production']

        master_config = copy.copy(bootstrap.DEFAULT_CONFIG)
        master_config['infrastructure_provisioning'] = 'test_cluster_type'
        master_config['owner'] = 'test_owner'
        master_config['aws_access_key'] = 'test_aws_access_key'
        master_config['aws_secret_file'] = 'test_aws_secret_file'
        master_config['ssh_key_file'] = 'test_ssh_key_file'
        master_config['ssh_key_name'] = 'test_ssh_key_name'
        master_config['directory'] = 'test_directory'
        master_config['production'] = True
        master_config['mc'] = 'test_mc'
        master_config['terraform'] = 'test_terraform'

        test_config = copy.copy(bootstrap.DEFAULT_CONFIG)
        test_config = bootstrap.parse_command_line(test_config, args)

        self.assertEquals(test_config, master_config)

    def test_copy_config_files(self):
        """Testing copy_config_files moves between dummy directories"""
        test_config = copy.copy(bootstrap.DEFAULT_CONFIG)
        test_dsipath = os.path.join(os.path.dirname(
            os.path.abspath(__file__)), 'test_dsipath')
        test_directory = os.path.join(os.path.dirname(
            os.path.abspath(__file__)), 'test_directory')
        # removing dirs if already exist
        try:
            shutil.rmtree(test_dsipath)
        except OSError:
            pass
        try:
            shutil.rmtree(test_directory)
        except OSError:
            pass
        os.makedirs(os.path.join(test_dsipath, 'configurations',
                                 'infrastructure_provisioning'))
        os.makedirs(os.path.join(test_dsipath, 'configurations',
                                 'mongodb_setup'))
        os.makedirs(os.path.join(test_dsipath, 'configurations',
                                 'test_control'))
        os.mkdir(test_directory)
        open(os.path.join(test_dsipath, 'configurations',
                          'infrastructure_provisioning',
                          'infrastructure_provisioning.single.yml'),
             'w').close()
        open(os.path.join(test_dsipath, 'configurations', 'mongodb_setup',
                          'mongodb_setup.replica.wiredTiger.yml'),
             'w').close()
        open(os.path.join(test_dsipath, 'configurations', 'test_control',
                          'test_control.core.yml'), 'w').close()
        test_config['infrastructure_provisioning'] = 'single'
        test_config['mongodb_setup'] = 'replica'
        test_config['storageEngine'] = 'wiredTiger'
        test_config['test_control'] = 'core'

        bootstrap.copy_config_files(test_dsipath, test_config, test_directory)
        master_files = set(['infrastructure_provisioning.yml',
                            'mongodb_setup.yml', 'test_control.yml'])
        test_files = set(os.listdir(test_directory))
        # cleaning up created dirs
        try:
            shutil.rmtree(test_dsipath)
            shutil.rmtree(test_directory)
        except OSError:
            pass
        self.assertEqual(test_files, master_files)

    def test_copy_config_files_ycsb(self):
        """Testing copy_config_files with ycsb flag"""
        test_config = copy.copy(bootstrap.DEFAULT_CONFIG)
        test_dsipath = os.path.join(os.path.dirname(
            os.path.abspath(__file__)), 'test_dsipath')
        test_directory = os.path.join(os.path.dirname(
            os.path.abspath(__file__)), 'test_directory')
        # removing dirs if already exist
        try:
            shutil.rmtree(test_dsipath)
        except OSError:
            pass
        try:
            shutil.rmtree(test_directory)
        except OSError:
            pass
        os.makedirs(os.path.join(
            test_dsipath, 'configurations', 'infrastructure_provisioning'))
        os.makedirs(os.path.join(
            test_dsipath, 'configurations', 'mongodb_setup'))
        os.makedirs(os.path.join(
            test_dsipath, 'configurations', 'test_control'))
        os.mkdir(test_directory)
        open(os.path.join(test_dsipath, 'configurations',
                          'infrastructure_provisioning',
                          'infrastructure_provisioning.shard.yml'),
             'w').close()
        open(os.path.join(test_dsipath, 'configurations', 'mongodb_setup',
                          'mongodb_setup.replica.wiredTiger.yml'),
             'w').close()
        open(os.path.join(test_dsipath, 'configurations', 'test_control',
                          'test_control.ycsb.multi_node.yml'),
             'w').close()
        test_config['infrastructure_provisioning'] = 'shard'
        test_config['mongodb_setup'] = 'replica'
        test_config['storageEngine'] = 'wiredTiger'
        test_config['test_control'] = 'ycsb'

        bootstrap.copy_config_files(test_dsipath, test_config, test_directory)
        master_files = set(['infrastructure_provisioning.yml',
                            'mongodb_setup.yml', 'test_control.yml'])
        test_files = set(os.listdir(test_directory))
        # cleaning up created dirs
        try:
            shutil.rmtree(test_dsipath)
            shutil.rmtree(test_directory)
        except OSError:
            pass
        self.assertEqual(test_files, master_files)

    @patch('os.path.exists')
    def test_setup_overrides_no_file_config_vals(self, mock_path_exists):
        """Testing setup_overrides where path = False and config vals given"""
        mock_path_exists.return_value = False
        config = copy.copy(bootstrap.DEFAULT_CONFIG)
        config['owner'] = 'testuser'
        config['ssh_key_name'] = 'test_ssh_key_name'
        config['ssh_key_file'] = 'test_ssh_key_file.pem'
        master_overrides = {}
        master_overrides.update({'infrastructure_provisioning': {'tfvars':{
            'ssh_key_file': 'test_ssh_key_file.pem',
            'ssh_key_name': 'test_ssh_key_name',
            'tags': {'owner': 'testuser'}}}})
        master_override_dict = master_overrides
        test_override_path = os.path.dirname(os.path.abspath(__file__))
        test_override_dict = {}

        # Call to setup_overrides creates 'overrides.yml' in current dir
        bootstrap.setup_overrides(config, test_override_path)
        with open(os.path.join(test_override_path,
                               'overrides.yml'), 'r') as test_override_file:
            test_override_dict = yaml.load(test_override_file)
        self.assertEqual(test_override_dict, master_override_dict)

        # Removing created file
        os.remove(os.path.join(test_override_path, 'overrides.yml'))

    def test_setup_overrides_file_exists_config_vals(self):
        """Testing setup_overrides where path = True and config vals given"""
        config = copy.copy(bootstrap.DEFAULT_CONFIG)
        config['owner'] = 'testuser1'
        config['ssh_key_name'] = 'test_ssh_key_name1'
        config['ssh_key_file'] = 'test_ssh_key_file1.pem'

        test_override_path = os.path.dirname(os.path.abspath(__file__))
        master_overrides = {}
        master_overrides.update({'infrastructure_provisioning': {'tfvars':{
            'ssh_key_file': 'test_ssh_key_file1.pem',
            'ssh_key_name': 'test_ssh_key_name1',
            'tags': {'owner': 'testuser1'}}}})
        master_override_dict = master_overrides
        test_override_str = yaml.dump({'infrastructure_provisioning': {
            'tfvars':{
                'ssh_key_file': 'test_ssh_key_file2.pem',
                'ssh_key_name': 'test_ssh_key_name2',
                'tags': {'owner': 'testuser2'}}}}, default_flow_style=False)

        # Creating 'overrides.yml' in current dir
        with open(os.path.join(test_override_path,
                               'overrides.yml'), 'w') as test_override_file:
            test_override_file.write(test_override_str)

        # Call to setup_overrides updates 'overrides.yml' in current dir
        bootstrap.setup_overrides(config, test_override_path)

        test_override_dict = {}
        with open(os.path.join(test_override_path,
                               'overrides.yml'), 'r') as test_override_file:
            test_override_dict = yaml.load(test_override_file)

        self.assertEqual(test_override_dict, master_override_dict)

        # Removing created file
        os.remove(os.path.join(test_override_path, 'overrides.yml'))

    @patch('os.path.exists')
    def test_setup_overrides_no_file_empty_config(self, mock_path_exists):
        """Testing setup_overrides, path = False and config vals not given"""
        mock_path_exists.return_value = False
        config = copy.copy(bootstrap.DEFAULT_CONFIG)
        config.pop('owner', None)
        config.pop('ssh_key_name', None)
        config.pop('ssh_key_file', None)
        test_override_path = os.path.dirname(os.path.abspath(__file__))

        master_overrides = {}
        master_overrides.update({'infrastructure_provisioning': {
            'tfvars': {}}})
        master_override_dict = master_overrides
        test_override_dict = {}

        # Call to setup_overrides creates 'overrides.yml' in current dir
        bootstrap.setup_overrides(config, test_override_path)

        with open(os.path.join(test_override_path,
                               'overrides.yml'), 'r') as test_override_file:
            test_override_dict = yaml.load(test_override_file)

        self.assertEqual(test_override_dict, master_override_dict)
        # Removing created file
        os.remove(os.path.join(test_override_path, 'overrides.yml'))

    def test_setup_overrides_file_exists_empty_config(self):
        """Testing setup_overrides, path = True and config vals not given"""
        config = copy.copy(bootstrap.DEFAULT_CONFIG)
        config.pop('owner', None)
        config.pop('ssh_key_name', None)
        config.pop('ssh_key_file', None)

        test_override_path = os.path.dirname(os.path.abspath(__file__))
        master_overrides = {}
        master_overrides.update({'infrastructure_provisioning': {
            'tfvars': {}}})
        master_override_dict = master_overrides
        test_override_str = yaml.dump({}, default_flow_style=False)

        # Creating 'overrides.yml' in current dir
        with open(os.path.join(test_override_path,
                               'overrides.yml'), 'w+') as test_override_file:
            test_override_file.write(test_override_str)

        # Call to setup_overrides updates 'overrides.yml' in current dir
        bootstrap.setup_overrides(config, test_override_path)

        test_override_dict = {}
        with open(os.path.join(test_override_path,
                               'overrides.yml'), 'r') as test_override_file:
            test_override_dict = yaml.load(test_override_file)

        self.assertEqual(test_override_dict, master_override_dict)

        # Removing created file
        os.remove(os.path.join(test_override_path, 'overrides.yml'))

    def test_setup_security_tf(self):
        """Testing setup_security_tf creates security.tf file"""
        config = copy.copy(bootstrap.DEFAULT_CONFIG)
        config['aws_access_key'] = 'test_aws_access_key'
        config['aws_secret_key'] = 'test_aws_secret_key'
        config['ssh_key_name'] = 'test_ssh_key_name'
        config['ssh_key_file'] = 'test_ssh_key_file.pem'

        master_tf_str = ('provider "aws" {    '
                         'access_key = "test_aws_access_key"    '
                         'secret_key = "test_aws_secret_key"    '
                         'region = "${var.region}"}'
                         'variable "key_name" {    '
                         'default = "test_ssh_key_name"}'
                         'variable "key_file" {    '
                         'default = "test_ssh_key_file.pem"}'
                        ).replace('\n', '').replace(' ', '')

        # Creating 'security.tf' file in current dir to test, reading to string
        test_tf_path = os.path.dirname(os.path.abspath(__file__))
        bootstrap.setup_security_tf(config, test_tf_path)
        test_tf_str = ''
        with open(os.path.join(test_tf_path,
                               'security.tf'), 'r') as test_tf_file:
            test_tf_str = test_tf_file.read().replace('\n',
                                                      '').replace(' ', '')
        self.assertEqual(test_tf_str, master_tf_str)

        # Removing created file
        os.remove(os.path.join(test_tf_path, 'security.tf'))


    @patch('subprocess.check_output')
    def test_find_terraform_no_except_terraform_in_config(self,
                                                          mock_check_output):
        """Testing find_terraform when no exception, val in config"""
        mock_check_output.return_value = '/usr/bin/terraform'
        config = copy.copy(bootstrap.DEFAULT_CONFIG)
        config['terraform'] = '/Users/testuser/config_override/terraform'
        terraform = bootstrap.find_terraform(config, '/')
        self.assertEqual(terraform,
                         '/Users/testuser/config_override/terraform')

    @patch('subprocess.check_output')
    def test_find_terraform_exception_terraform_in_config(self,
                                                          mock_check_output):
        """Testing find_terraform throws exception when val in config"""
        mock_check_output.side_effect = subprocess.CalledProcessError('Test',
                                                                      1)
        config = copy.copy(bootstrap.DEFAULT_CONFIG)
        config['terraform'] = '/Users/testuser/config_override/terraform'
        terraform = bootstrap.find_terraform(config, '/')
        self.assertEqual(terraform,
                         '/Users/testuser/config_override/terraform')

    @patch('subprocess.check_output')
    def test_find_terraform_no_except_tf_not_in_config(self,
                                                       mock_check_output):
        """Testing find_terraform when no exception, val not in config"""
        mock_check_output.return_value = '/usr/bin/terraform'
        config = copy.copy(bootstrap.DEFAULT_CONFIG)
        config.pop('terraform', None)
        terraform = bootstrap.find_terraform(config, '/')
        self.assertEqual(terraform, '/usr/bin/terraform')

    @patch('subprocess.check_output')
    def test_find_terraform_exception_tf_not_in_config(self,
                                                       mock_check_output):
        """Testing find_terraform throws exception when val not in config"""
        mock_check_output.side_effect = subprocess.CalledProcessError('Test',
                                                                      1)
        config = copy.copy(bootstrap.DEFAULT_CONFIG)
        config.pop('terraform', None)
        terraform = bootstrap.find_terraform(config, '/Users/testuser/default')
        self.assertEqual(terraform, '/Users/testuser/default/terraform')


    @patch('subprocess.check_output')
    def test_terraform_wrong_version(self,
                                     mock_check_output):
        """Testing validate_terraform fails on incorrect version"""
        mock_check_output.return_value = "Terraform v0.6.16"
        config = copy.copy(bootstrap.DEFAULT_CONFIG)
        with LogCapture(level=logging.CRITICAL) as crit:
            with self.assertRaises(AssertionError):
                bootstrap.validate_terraform(config)
            crit_logs = set(crit.actual())
            crit_expected = set([('bootstrap', 'CRITICAL',
                                  'You are using Terraform v0.6.16, '
                                  'but DSI requires Terraform v0.9.11.'),
                                 ('bootstrap', 'CRITICAL',
                                  'See documentation for installing terraform: '
                                  'http://bit.ly/2ufjQ0R')])
            self.assertTrue(crit_expected.issubset(crit_logs))

    @patch('subprocess.check_output')
    def test_terraform_call_fails(self,
                                  mock_check_output):
        """Testing validate_terraform fails when terraform call fails"""
        mock_check_output.side_effect = subprocess.CalledProcessError(1, None)
        mock_check_output.return_value = "Terraform v0.6.16"
        config = copy.copy(bootstrap.DEFAULT_CONFIG)
        with LogCapture(level=logging.CRITICAL) as crit:
            with self.assertRaises(AssertionError):
                bootstrap.validate_terraform(config)
            crit_logs = set(crit.actual())
            crit_expected = set([('bootstrap', 'CRITICAL',
                                  'Call to terraform failed.'),
                                 ('bootstrap', 'CRITICAL',
                                  'See documentation for installing terraform: '
                                  'http://bit.ly/2ufjQ0R')])
            self.assertTrue(crit_expected.issubset(crit_logs))

    @patch('subprocess.check_output')
    def test_terraform_cannot_execute(self,
                                      mock_check_output):
        """Testing validate_terraform fails when terraform doesn't run"""
        mock_check_output.side_effect = subprocess.CalledProcessError(126, None)
        mock_check_output.return_value = "Terraform v0.6.16"
        config = copy.copy(bootstrap.DEFAULT_CONFIG)
        with LogCapture(level=logging.CRITICAL) as crit:
            with self.assertRaises(AssertionError):
                bootstrap.validate_terraform(config)
            crit_logs = set(crit.actual())
            crit_expected = set([('bootstrap', 'CRITICAL',
                                  'Cannot execute terraform binary file.'),
                                 ('bootstrap', 'CRITICAL',
                                  'See documentation for installing terraform: '
                                  'http://bit.ly/2ufjQ0R')])
            self.assertTrue(crit_expected.issubset(crit_logs))

    @patch('subprocess.check_output')
    def test_terraform_not_found(self,
                                 mock_check_output):
        """Testing validate_terraform fails when terraform is not found"""
        mock_check_output.side_effect = subprocess.CalledProcessError(127, None)
        mock_check_output.return_value = "Terraform v0.6.16"
        config = copy.copy(bootstrap.DEFAULT_CONFIG)
        with LogCapture(level=logging.CRITICAL) as crit:
            with self.assertRaises(AssertionError):
                bootstrap.validate_terraform(config)
            crit_logs = set(crit.actual())
            crit_expected = set([('bootstrap', 'CRITICAL',
                                  'No terraform binary file found.'),
                                 ('bootstrap', 'CRITICAL',
                                  'See documentation for installing terraform: '
                                  'http://bit.ly/2ufjQ0R')])
            self.assertTrue(crit_expected.issubset(crit_logs))

    @patch('subprocess.check_output')
    def test_terraform_valid(self, mock_check_output):
        """Testing validate_terraform with valid inputs"""
        mock_check_output.return_value = 'Terraform v0.9.11'
        config = copy.copy(bootstrap.DEFAULT_CONFIG)
        bootstrap.validate_terraform(config)
        self.assertEquals(config, config)

    @patch('subprocess.Popen')
    def test_mc_valid(self, mock_popen):
        """Testing validate_mission_control with valid inputs"""
        mock_popen.return_value.communicate.return_value = ('', 'Usage of mc:')
        #print mock_popen.communicate[1].split('\n')[0]
        config = copy.copy(bootstrap.DEFAULT_CONFIG)
        bootstrap.validate_mission_control(config)
        self.assertEquals(config, config)

    @patch('subprocess.Popen.communicate')
    def test_mission_control_not_on_path(self,
                                         mock_popen):
        """Testing validate_mission_control fails when not on path"""
        mock_popen.side_effect = OSError
        config = copy.copy(bootstrap.DEFAULT_CONFIG)
        with LogCapture(level=logging.CRITICAL) as crit:
            with self.assertRaises(AssertionError):
                bootstrap.validate_mission_control(config)
            crit_logs = set(crit.actual())
            crit_expected = set([('bootstrap', 'CRITICAL',
                                  'mission-control binary file not found.'),
                                 ('bootstrap', 'CRITICAL',
                                  'See documentation for installing mission-control: '
                                  'http://bit.ly/2ufjQ0R')])
            self.assertTrue(crit_expected.issubset(crit_logs))

    @patch('subprocess.Popen')
    def test_mission_control_call_failed(self,
                                         mock_popen):
        """Testing validate_mission_control fails when 'mc -h' fails"""
        mock_popen.return_value.communicate.return_value = ('', '')
        config = copy.copy(bootstrap.DEFAULT_CONFIG)
        with LogCapture(level=logging.CRITICAL) as crit:
            with self.assertRaises(AssertionError):
                bootstrap.validate_mission_control(config)
            crit_logs = set(crit.actual())
            crit_expected = set([('bootstrap', 'CRITICAL',
                                  'Call to mission-control failed.'),
                                 ('bootstrap', 'CRITICAL',
                                  'See documentation for installing mission-control: '
                                  'http://bit.ly/2ufjQ0R')])
            self.assertTrue(crit_expected.issubset(crit_logs))

    @patch('subprocess.check_output')
    def test_find_mission_control_no_except_mc_in_config(self,
                                                         mock_check_output):
        """Testing find_mission_control when no exception, val in config"""
        mock_check_output.return_value = '/usr/bin/mc'
        config = copy.copy(bootstrap.DEFAULT_CONFIG)
        config['mc'] = '/Users/testuser/config_override/mc'
        mission_control = bootstrap.find_mission_control(config,
                                                         '/Users/testuser/dsi')
        self.assertEqual(mission_control, '/Users/testuser/config_override/mc')

    @patch('subprocess.check_output')
    def test_find_mission_control_exception_mc_in_config(self,
                                                         mock_check_output):
        """Testing find_mission_control when throws exception, val in config"""
        mock_check_output.side_effect = subprocess.CalledProcessError('Test',
                                                                      1)
        config = copy.copy(bootstrap.DEFAULT_CONFIG)
        config['mc'] = '/Users/testuser/config_override/mc'
        mission_control = bootstrap.find_mission_control(config,
                                                         '/Users/testuser/dsi')
        self.assertEqual(mission_control, '/Users/testuser/config_override/mc')

    @patch('subprocess.check_output')
    def test_find_mission_control_no_except_mc_not_in_config(self,
                                                             mock_check_output):
        """Testing find_mission_control when no exception, val not in config"""
        mock_check_output.return_value = '/usr/bin/mc'
        config = copy.copy(bootstrap.DEFAULT_CONFIG)
        config.pop('mc', None)
        mission_control = bootstrap.find_mission_control(config,
                                                         '/Users/testuser/dsi')
        self.assertEqual(mission_control, '/usr/bin/mc')

    @patch('subprocess.check_output')
    def test_find_mission_control_exception_mc_not_in_config(self,
                                                             mock_check_output):
        """Testing find_mission_control throws exception, val not in config"""
        mock_check_output.side_effect = subprocess.CalledProcessError('Test', 1)
        config = copy.copy(bootstrap.DEFAULT_CONFIG)
        config.pop('mc', None)
        mission_control = bootstrap.find_mission_control(config,
                                                         '/Users/testuser/dsi')
        self.assertEqual(mission_control, '/Users/testuser/dsi/bin/mc')

    def test_write_dsienv(self):
        """Testing write_dsienv with workloads and ycsb paths specified"""
        directory = os.path.dirname(os.path.abspath(__file__))
        dsipath = "/Users/test_user/dsipath"
        mission_control = "/Users/test_user/mc"
        terraform = "/Users/test_user/terraform"
        config = {"workloads_dir": "/Users/test_user/workloads",
                  "ycsb_dir": "/Users/test_user/ycsb"}

        master_dsienv = ('export DSI_PATH=/Users/test_user/dsipath\n'
                         'export PATH=/Users/test_user/dsipath/bin:$PATH\n'
                         'export MC=/Users/test_user/mc\n'
                         'export TERRAFORM=/Users/test_user/terraform\n'
                         'export WORKLOADS_DIR=/Users/test_user/workloads\n'
                         'export YCSB_DIR=/Users/test_user/ycsb')
        bootstrap.write_dsienv(directory, dsipath, mission_control, terraform, config)

        with open(os.path.join(directory, "dsienv.sh")) as dsienv:
            test_dsienv = dsienv.read()
            self.assertEqual(test_dsienv, master_dsienv)
        os.remove(os.path.join(directory, "dsienv.sh"))

    def test_write_dsienv_no_workloads_or_ycsb(self):
        """Testing write_dsienv without workloads or ycsb paths specified"""
        directory = os.path.dirname(os.path.abspath(__file__))
        dsipath = "/Users/test_user/dsipath"
        mission_control = "/Users/test_user/mc"
        terraform = "/Users/test_user/terraform"
        config = {}
        master_dsienv = ('export DSI_PATH=/Users/test_user/dsipath\n'
                         'export PATH=/Users/test_user/dsipath/bin:$PATH\n'
                         'export MC=/Users/test_user/mc\n'
                         'export TERRAFORM=/Users/test_user/terraform')
        bootstrap.write_dsienv(directory, dsipath, mission_control, terraform, config)

        with open(os.path.join(directory, "dsienv.sh")) as dsienv:
            test_dsienv = dsienv.read()
            self.assertEqual(test_dsienv, master_dsienv)
        os.remove(os.path.join(directory, "dsienv.sh"))

if __name__ == '__main__':
    unittest.main()
