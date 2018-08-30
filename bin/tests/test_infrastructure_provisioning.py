"""
Unit test for infrastructure_provisioning.py
"""

from functools import partial
from subprocess import CalledProcessError
import copy
import glob
import logging
import os
import shutil
import unittest

from mock import patch, call, mock_open, MagicMock, ANY
from testfixtures import LogCapture, log_capture

import infrastructure_provisioning as ip
from test_lib.fixture_files import FixtureFiles
import test_lib.structlog_for_test as structlog_for_test

#pylint: disable=too-many-locals

FIXTURE_FILES = FixtureFiles(os.path.dirname(__file__))


class TestInfrastructureProvisioning(unittest.TestCase):
    """
    Test suite for infrastructure_provisioning.py
    """

    def setUp(self):
        self.os_environ_patcher = patch('infrastructure_provisioning.os.environ')
        self.mock_environ = self.os_environ_patcher.start()
        self.dsi_path = os.path.dirname(
            os.path.dirname(os.path.abspath(os.path.join(__file__, '..'))))
        self.reset_mock_objects()
        self.config = {
            'bootstrap': {
                'infrastructure_provisioning': 'single'
            },
            'infrastructure_provisioning': {
                'terraform': {
                    'aws_required_version': 'test_aws_version'
                },
                'tfvars': {
                    'cluster_name': 'single',
                    'ssh_key_file': 'aws_ssh_key.pem',
                    'ssh_key_name': 'serverteam-perf-ssh-key'
                },
                'evergreen': {
                    'data_dir': FIXTURE_FILES.fixture_dir_path
                }
            },
            'runtime_secret': {
                'aws_access_key': 'test_access_key',
                'aws_secret_key': 'test_secret_key'
            }
        }
        # create a provision log path that can be safely deleted post test
        self.provision_log_path = os.path.join(FIXTURE_FILES.fixture_dir_path,
                                               ip.PROVISION_LOG_PATH)

        # Setup logging so that structlog uses stdlib, and LogCapture works
        structlog_for_test.setup_logging()

    def tearDown(self):
        self.os_environ_patcher.stop()
        if os.path.exists(self.provision_log_path):
            os.remove(self.provision_log_path)

    def reset_mock_objects(self):
        """
        Used to reset environment variables and mock objects
        """
        self.os_environ = {'TERRAFORM': 'test/path/terraform', 'DSI_PATH': self.dsi_path}
        self.mock_environ.__getitem__.side_effect = self.os_environ.__getitem__
        self.mock_environ.__contains__.side_effect = self.os_environ.__contains__
        self.mock_environ.__delitem__.side_effect = self.os_environ.__delitem__

    def check_subprocess_call(self, command_to_check, command, env=None):
        """
        Needed to properly check subprocess.check_call since __file__ is used
        to find the path to the file being executed.
        :param command_to_check list that represents the expected command
        :param command is the command subprocess.check_call tries to run. This command is checked
        against command_to_check based on the file in the commands.
        :param env dict that represents the environment variables passed into subprocess.check_call
        """
        if len(command_to_check) > 1:
            if command_to_check[1].endswith('infrastructure_teardown.py'):
                self.assertTrue('TERRAFORM' not in env)
        else:
            if command_to_check[0].endswith('infrastructure_teardown.sh'):
                self.assertTrue('TERRAFORM' not in env)
        self.assertEqual(command_to_check, command)

    def test_provisioner_init(self):
        """
        Test Provisioner.__init__
        """
        # Check that the correct default provisioning log is created
        mock_open_file = mock_open()
        with patch('infrastructure_provisioning.open', mock_open_file, create=True):
            ip.Provisioner(self.config)
            mock_open_file.assert_called_with(ip.PROVISION_LOG_PATH, "w")

        # Check when TERRAFORM is an environment variable
        provisioner = ip.Provisioner(self.config, provisioning_file=self.provision_log_path)
        self.assertEqual(provisioner.cluster, 'single')
        self.assertFalse(provisioner.reuse_cluster)
        self.assertEqual(provisioner.dsi_dir, self.dsi_path)
        self.assertFalse(provisioner.existing)
        self.assertEqual(provisioner.parallelism, '-parallelism=20')
        self.assertEqual(provisioner.terraform, 'test/path/terraform')

        # Check when TERRAFORM is not environment variable
        os_environ_missing_terraform = self.os_environ.copy()
        del os_environ_missing_terraform['TERRAFORM']
        self.mock_environ.__getitem__.side_effect = os_environ_missing_terraform.__getitem__
        self.mock_environ.__contains__.side_effect = os_environ_missing_terraform.__contains__
        provisioner_missing_terraform = ip.Provisioner(
            self.config, provisioning_file=self.provision_log_path)
        self.assertEqual(provisioner_missing_terraform.cluster, 'single')
        self.assertFalse(provisioner_missing_terraform.reuse_cluster)
        self.assertEqual(provisioner_missing_terraform.dsi_dir, self.dsi_path)
        self.assertFalse(provisioner_missing_terraform.existing)
        self.assertEqual(provisioner_missing_terraform.parallelism, '-parallelism=20')
        self.assertEqual(provisioner_missing_terraform.terraform, './terraform')
        self.reset_mock_objects()

    def test_setup_security_tf(self):
        """
        Testing setup_security_tf creates security.tf file
        """
        key_name = self.config['infrastructure_provisioning']['tfvars']['ssh_key_name']
        key_file = self.config['infrastructure_provisioning']['tfvars']['ssh_key_file']
        master_tf_str = ('provider "aws" {{    '
                         'access_key = "test_aws_access_key"    '
                         'secret_key = "test_aws_secret_key"    '
                         'region = "${{var.region}}"'
                         'version = "test_aws_version" }}'
                         'variable "key_name" {{    '
                         'default = "{}"}}'
                         'variable "key_file" {{    '
                         'default = "{}"}}').format(key_name, key_file)
        master_tf_str = master_tf_str.replace('\n', '').replace(' ', '')
        provisioner = ip.Provisioner(self.config, provisioning_file=self.provision_log_path)
        provisioner.aws_access_key = 'test_aws_access_key'
        provisioner.aws_secret_key = 'test_aws_secret_key'

        # Creating 'security.tf' file in current dir to test, reading to string
        provisioner.setup_security_tf()
        test_tf_str = ''
        with open('security.tf', 'r') as test_tf_file:
            test_tf_str = test_tf_file.read().replace('\n', '').replace(' ', '')
        self.assertEqual(test_tf_str, master_tf_str)

        # Removing created file
        os.remove('security.tf')

    def test_setup_terraform_tf(self):
        """
        Test setup_terraform_tf creates the correct directories and files
        """
        # Create temporary directory and get correct paths
        directory = 'temp_test'
        if os.path.exists(directory):
            shutil.rmtree(directory)
        os.mkdir(directory)
        cluster_path = os.path.join(self.dsi_path, 'clusters', 'default')
        remote_scripts_path = os.path.join(self.dsi_path, 'clusters', 'remote-scripts')
        remote_scripts_target = os.path.join(directory, 'remote-scripts')
        modules_path = os.path.join(self.dsi_path, 'clusters', 'modules')
        modules_target = os.path.join(directory, 'modules')

        # Check files copied correctly
        with patch('infrastructure_provisioning.os.getcwd', return_value='temp_test'):
            provisioner = ip.Provisioner(self.config, provisioning_file=self.provision_log_path)
            provisioner.setup_terraform_tf()
        for filename in glob.glob(os.path.join(cluster_path, '*')):
            self.assertTrue(os.path.exists(os.path.join(directory, filename.split('/')[-1])))
        for filename in glob.glob(os.path.join(remote_scripts_path, '*')):
            self.assertTrue(os.path.exists(os.path.join(remote_scripts_target, \
                                                        filename.split('/')[-1])))
        for filename in glob.glob(os.path.join(modules_path, '*')):
            self.assertTrue(os.path.exists(os.path.join(modules_target, filename.split('/')[-1])))

        # Remove temporary directory
        shutil.rmtree(directory)

    @patch('infrastructure_provisioning.shutil.copyfile')
    @patch('infrastructure_provisioning.subprocess.check_call')
    @patch('infrastructure_provisioning.os.path.isdir')
    @patch('infrastructure_provisioning.rmtree_when_present')
    def test_check_existing_state(self, mock_rmtree, mock_isdir, mock_check_call, mock_copyfile):
        """
        Test Provisioner.existing_state. First case finds a saved state, second doesn't
        """
        config = copy.deepcopy(self.config)
        config['infrastructure_provisioning']['tfvars']['cluster_name'] = 'replica'

        evg_data_dir = config['infrastructure_provisioning']['evergreen']['data_dir']
        mock_isdir.side_effect = lambda evg_dir: evg_dir == evg_data_dir
        # Run check_existing_state when existing state exists
        with patch('infrastructure_provisioning.os.path.isfile') as mock_isfile:
            mock_isfile.return_value = True
            provisioner = ip.Provisioner(config, provisioning_file=self.provision_log_path)
            mock_teardown_old_cluster = MagicMock(name="teardown_old_cluster")
            self.assertEqual(provisioner.evg_data_dir, evg_data_dir)
            provisioner.check_existing_state()
            isfile_calls = [
                call(evg_data_dir + 'terraform/terraform.tfstate'),
                call(evg_data_dir + 'terraform/provisioned.replica')
            ]
            mock_isfile.assert_has_calls(isfile_calls)
            copyfile_calls = [
                call(
                    FIXTURE_FILES.fixture_file_path('terraform/terraform.tfstate'),
                    './terraform.tfstate'),
                call(FIXTURE_FILES.fixture_file_path('terraform/cluster.json'), 'cluster.json')
            ]
            mock_copyfile.assert_has_calls(copyfile_calls)
            mock_check_call.assert_not_called()
            mock_rmtree.assert_not_called()
            self.assertTrue(provisioner.existing)
            mock_teardown_old_cluster.assert_not_called()

        with patch('infrastructure_provisioning.os.path.isfile') as mock_isfile:
            with patch('infrastructure_provisioning.check_version') as mock_check_version:
                mock_check_version.return_value = False
                mock_isfile.return_value = True
                provisioner = ip.Provisioner(config, provisioning_file=self.provision_log_path)
                mock_teardown_old_cluster = MagicMock(name="teardown_old_cluster")
                provisioner.teardown_old_cluster = mock_teardown_old_cluster
                self.assertEqual(provisioner.evg_data_dir, evg_data_dir)
                provisioner.check_existing_state()
                mock_teardown_old_cluster.assert_called_once()
                self.assertFalse(provisioner.existing)
                mock_check_version.assert_called_once_with(
                    FIXTURE_FILES.fixture_file_path('terraform/provisioned.replica'))

        # Run check_existing_state when no existing state exists
        with patch('infrastructure_provisioning.os.path.isfile') as mock_isfile:
            mock_isfile.return_value = False
            provisioner = ip.Provisioner(config, provisioning_file=self.provision_log_path)
            provisioner.check_existing_state()
            isfile_calls = [call(evg_data_dir + 'terraform/terraform.tfstate')]
            mock_isfile.assert_has_calls(isfile_calls)
            mock_check_call.assert_not_called()
            mock_rmtree.assert_not_called()
            self.assertFalse(provisioner.existing)
        self.reset_mock_objects()

    @patch('infrastructure_provisioning.shutil')
    @patch('infrastructure_provisioning.subprocess.check_call')
    @patch('infrastructure_provisioning.os.path.isdir')
    @patch('infrastructure_provisioning.os.remove')
    def test_check_existing_state_initialsync(self, mock_remove, mock_isdir, mock_check_call,
                                              mock_shutil):
        """
        Test Provisioner.existing_state, initialsync-logkeeper should force destroy existing
        """
        config = copy.deepcopy(self.config)
        config['infrastructure_provisioning']['tfvars']['cluster_name'] = 'initialsync-logkeeper'

        evg_data_dir = config['infrastructure_provisioning']['evergreen']['data_dir']
        mock_isdir.side_effect = lambda evg_dir: evg_dir == evg_data_dir
        # Run check_existing_state when existing state exists
        with patch('infrastructure_provisioning.os.path.isfile') as mock_isfile:
            expected_command = ['python', evg_data_dir + 'terraform/infrastructure_teardown.py']
            # mock_check_call.side_effect = partial(self.check_subprocess_call, expected_command)
            mock_isfile.return_value = True
            provisioner = ip.Provisioner(config, provisioning_file=self.provision_log_path)
            self.assertEqual(provisioner.evg_data_dir, evg_data_dir)
            provisioner.check_existing_state()
            mock_check_call.assert_called_with(expected_command, env=ANY, stdout=ANY, stderr=ANY)
            mock_shutil.rmtree.assert_called_with(evg_data_dir)
            isfile_calls = [
                call(FIXTURE_FILES.fixture_file_path('terraform/infrastructure_teardown.py')),
                call('cluster.json'),
                call('terraform.tfstate'),
                call(FIXTURE_FILES.fixture_file_path('terraform/terraform.tfstate')),
                call(
                    FIXTURE_FILES.fixture_file_path('terraform/provisioned.initialsync-logkeeper'))
            ]
            mock_isfile.assert_has_calls(isfile_calls)
            remove_calls = [call('cluster.json'), call('terraform.tfstate')]
            mock_remove.assert_has_calls(remove_calls)
            self.assertTrue(provisioner.existing)

        # Run check_existing_state when no existing state exists
        with patch('infrastructure_provisioning.os.path.isfile') as mock_isfile:
            expected_command = [
                FIXTURE_FILES.fixture_file_path('terraform/infrastructure_teardown.sh')
            ]
            mock_check_call.side_effect = partial(self.check_subprocess_call, expected_command)
            mock_isfile.return_value = False
            provisioner = ip.Provisioner(config, provisioning_file=self.provision_log_path)
            provisioner.check_existing_state()
            mock_shutil.rmtree.assert_called_with(evg_data_dir)
            isfile_calls = [call(evg_data_dir + 'terraform/terraform.tfstate')]
            mock_isfile.assert_has_calls(isfile_calls)
            remove_calls = [call('cluster.json'), call('terraform.tfstate')]
            mock_remove.assert_has_calls(remove_calls)
            self.assertFalse(provisioner.existing)
        self.reset_mock_objects()

    @patch('infrastructure_provisioning.shutil')
    @patch('infrastructure_provisioning.subprocess.check_call')
    @patch('infrastructure_provisioning.os.path.isdir')
    @patch('infrastructure_provisioning.os.remove')
    def test_check_existing_state_teardown_fails(self, mock_remove, mock_isdir, mock_check_call,
                                                 mock_shutil):
        """
        Test Provisioner.existing_state when teardown fails. The code should catch the exception,
        and continue execution.
        """
        config = copy.deepcopy(self.config)
        config['infrastructure_provisioning']['tfvars']['cluster_name'] = 'single'

        evg_data_dir = config['infrastructure_provisioning']['evergreen']['data_dir']
        mock_isdir.side_effect = lambda evg_dir: evg_dir == evg_data_dir
        with patch('infrastructure_provisioning.os.path.isfile') as mock_isfile:
            mock_check_call.side_effect = CalledProcessError(1, ['cmd'])
            mock_isfile.return_value = True
            provisioner = ip.Provisioner(config, provisioning_file=self.provision_log_path)
            self.assertEqual(provisioner.evg_data_dir, evg_data_dir)
            with LogCapture(level=logging.ERROR) as error:
                provisioner.check_existing_state()
                error.check((
                    'infrastructure_provisioning',
                    'ERROR',
                    "[error    ] Teardown of existing resources failed. Catching exception and continuing. [infrastructure_provisioning] \nCommand '['cmd']' returned non-zero exit status 1"  # pylint: disable=line-too-long
                ))
            mock_shutil.rmtree.assert_called_with(evg_data_dir)
            isfile_calls = [
                call(FIXTURE_FILES.fixture_file_path('terraform/terraform.tfstate')),
                call(FIXTURE_FILES.fixture_file_path('terraform/provisioned.single')),
                call(FIXTURE_FILES.fixture_file_path('terraform/infrastructure_teardown.py')),
                call('cluster.json'),
                call('terraform.tfstate')
            ]
            # This call to check_existing_state should follow the same path as the working case,
            # through the sub_process.check_call. As such, it should have the same isfile calls as
            # that case.
            mock_isfile.assert_has_calls(isfile_calls)
            remove_calls = [call('cluster.json'), call('terraform.tfstate')]
            mock_remove.assert_has_calls(remove_calls)
            self.assertFalse(provisioner.existing)

        self.reset_mock_objects()

    @patch('infrastructure_provisioning.shutil')
    @patch('infrastructure_provisioning.os.listdir')
    @patch('infrastructure_provisioning.os.path.isdir')
    @patch('infrastructure_provisioning.os.chmod')
    def test_setup_evg_dir(self, mock_chmod, mock_isdir, mock_listdir, mock_shutil):
        """
        Test Provisioner.setup_evg_dir
        """
        evg_data_dir = self.config['infrastructure_provisioning']['evergreen']['data_dir']
        # Test when evergreen data directories do not exist
        with patch('infrastructure_provisioning.os.makedirs') as mock_makedirs:
            mock_isdir.return_value = False
            provisioner = ip.Provisioner(self.config, provisioning_file=self.provision_log_path)
            provisioner.bin_dir = 'test/bin'
            provisioner.setup_evg_dir()
            mock_makedirs.assert_called_with(evg_data_dir)
            copytree_calls = [
                call('../terraform', evg_data_dir + 'terraform'),
                call('./modules', evg_data_dir + 'terraform/modules')
            ]
            mock_shutil.copytree.assert_has_calls(copytree_calls)
            copyfile_calls = [
                call(provisioner.bin_dir + '/infrastructure_teardown.py',
                     evg_data_dir + 'terraform/infrastructure_teardown.py')
            ]
            mock_shutil.copyfile.assert_has_calls(copyfile_calls)
            listdir_calls = [call(evg_data_dir), call(os.path.join(evg_data_dir, 'terraform'))]
            # any_order is set to True because when running nosetests, listdir has extra
            # __str__() calls due to logging
            mock_listdir.assert_has_calls(listdir_calls, any_order=True)
            mock_chmod.assert_called_with(
                os.path.join(evg_data_dir, 'terraform/infrastructure_teardown.py'), 0755)

        # Test when evergreen data directories do exist
        with patch('infrastructure_provisioning.os.makedirs') as mock_makedirs:
            mock_isdir.return_value = True
            provisioner = ip.Provisioner(self.config, provisioning_file=self.provision_log_path)
            provisioner.bin_dir = 'test/bin'
            provisioner.setup_evg_dir()
            self.assertFalse(mock_makedirs.called)
            mock_chmod.assert_called_with(
                os.path.join(evg_data_dir, 'terraform/infrastructure_teardown.py'), 0755)
        self.reset_mock_objects()

    @patch('infrastructure_provisioning.Provisioner.setup_terraform_tf')
    @patch('infrastructure_provisioning.Provisioner.setup_security_tf')
    @patch('infrastructure_provisioning.Provisioner.setup_evg_dir')
    @patch('infrastructure_provisioning.Provisioner.save_terraform_state')
    @patch('infrastructure_provisioning.TerraformOutputParser')
    @patch('infrastructure_provisioning.TerraformConfiguration')
    @patch('infrastructure_provisioning.run_and_save_output')
    @patch('infrastructure_provisioning.subprocess')
    def test_setup_cluster(self, mock_subprocess, mock_save_output, mock_terraform_configuration,
                           mock_terraform_output_parser, mock_save_terraform_state,
                           mock_setup_evg_dir, mock_setup_security_tf, mock_setup_terraform_tf):
        """
        Test Provisioner.setup_cluster
        """
        # NOTE: This tests the majority of the functionality of the infrastructure_provisioning.py
        # mock.mock_open is needed to effectively mock out the open() function in python
        mock_open_file = mock_open()
        with patch('infrastructure_provisioning.open', mock_open_file, create=True):
            provisioner = ip.Provisioner(self.config, provisioning_file=self.provision_log_path)
            provisioner.cluster = 'initialsync-logkeeper'
            provisioner.reuse_cluster = True
            provisioner.setup_cluster()
            mock_setup_security_tf.assert_called()
            mock_setup_terraform_tf.assert_called()
            mock_terraform_configuration.return_value.to_json.assert_called_with(
                file_name='cluster.json')
            # __enter__ and __exit__ are checked to see if the files were opened
            # as context managers.
            open_file_calls = [call('infrastructure_provisioning.out.yml', 'r'), call().read()]
            mock_open_file.assert_has_calls(open_file_calls, any_order=True)
            # If the cluster is initialsync-logkeeper, then terraform should be run twice
            terraform = self.os_environ['TERRAFORM']
            check_call_calls = [
                call(
                    [terraform, 'init', '-upgrade'],
                    stdout=provisioner.stdout,
                    stderr=provisioner.stderr),
                call(
                    [
                        terraform, 'apply', '-var-file=cluster.json', provisioner.parallelism,
                        '-var="mongod_ebs_instance_count=0"', '-var="workload_instance_count=0"'
                    ],
                    stdout=provisioner.stdout,
                    stderr=provisioner.stderr),
                call(
                    [terraform, 'apply', '-var-file=cluster.json', provisioner.parallelism],
                    stdout=provisioner.stdout,
                    stderr=provisioner.stderr),
                call(
                    [terraform, 'refresh', '-var-file=cluster.json'],
                    stdout=provisioner.stdout,
                    stderr=provisioner.stderr),
                call(
                    [terraform, 'plan', '-detailed-exitcode', '-var-file=cluster.json'],
                    stdout=provisioner.stdout,
                    stderr=provisioner.stderr)
            ]
            mock_subprocess.check_call.assert_has_calls(check_call_calls)
            mock_save_output.assert_called_with([terraform, 'output'])
            self.assertTrue(mock_terraform_output_parser.return_value.write_output_files.called)
            self.assertTrue(mock_setup_evg_dir.called)
            self.assertTrue(mock_save_terraform_state.called)
        self.reset_mock_objects()

    @patch('infrastructure_provisioning.Provisioner.setup_terraform_tf')
    @patch('infrastructure_provisioning.shutil.rmtree')
    @patch('infrastructure_provisioning.Provisioner.save_terraform_state')
    @patch('infrastructure_provisioning.TerraformOutputParser')
    @patch('infrastructure_provisioning.TerraformConfiguration')
    @patch('infrastructure_provisioning.subprocess')
    def test_setup_cluster_failure(self, mock_subprocess, mock_terraform_configuration,
                                   mock_terraform_output_parser, mock_save_terraform_state,
                                   mock_rmtree, mock_setup_terraform_tf):
        """
        Test Provisioner.setup_cluster when an error happens. Ensure that the cluster is torn
        down.
        """
        # NOTE: This tests the majority of the functionality of the infrastructure_provisioning.py
        mock_open_file = mock_open()
        with patch('infrastructure_provisioning.open', mock_open_file, create=True):
            with patch('infrastructure_provisioning.destroy_resources') as mock_destroy:
                provisioner = ip.Provisioner(self.config, provisioning_file=self.provision_log_path)
                provisioner.reuse_cluster = True
                mock_subprocess.check_call.side_effect = [1, CalledProcessError(1, ['cmd']), 1]
                with self.assertRaises(CalledProcessError):
                    provisioner.setup_cluster()
            mock_setup_terraform_tf.assert_called()
            mock_destroy.assert_called()
            mock_rmtree.assert_called()
            self.assertFalse(mock_terraform_output_parser.return_value.write_output_files.called)
            self.assertFalse(mock_save_terraform_state.called)
            mock_terraform_configuration.return_value.to_json.assert_called_with(
                file_name='cluster.json')
        self.reset_mock_objects()

    @patch('infrastructure_provisioning.subprocess.check_call')
    @patch('infrastructure_provisioning.os.remove')
    @patch('infrastructure_provisioning.os.chdir')
    @patch('infrastructure_provisioning.os.getcwd')
    @patch('infrastructure_provisioning.shutil.copyfile')
    def test_save_terraform_state(self, mock_copyfile, mock_getcwd, mock_chdir, mock_remove,
                                  mock_check_call):
        """
        Test Provisioner.save_terraform_state
        """
        provisioned_files = ['provisioned.single', 'provisioned.shard']
        evg_data_dir = self.config['infrastructure_provisioning']['evergreen']['data_dir']
        terraform_dir = os.path.join(evg_data_dir, 'terraform')
        with patch('infrastructure_provisioning.glob.glob') as mock_glob:
            mock_open_file = mock_open()
            with patch('infrastructure_provisioning.open', mock_open_file, create=True):
                mock_glob.return_value = provisioned_files
                mock_getcwd.return_value = 'fake/path'
                provisioner = ip.Provisioner(self.config, provisioning_file=self.provision_log_path)
                provisioner.production = True
                provisioner.save_terraform_state()
                files_to_copy = [
                    'terraform.tfstate', 'cluster.tf', 'security.tf', 'cluster.json',
                    'aws_ssh_key.pem'
                ]
                copyfile_calls = [
                    call(file_to_copy, os.path.join(terraform_dir, file_to_copy))
                    for file_to_copy in files_to_copy
                ]
                mock_copyfile.assert_has_calls(copyfile_calls)
                chdir_calls = [call(terraform_dir), call(mock_getcwd.return_value)]
                mock_chdir.assert_has_calls(chdir_calls)
                mock_check_call.assert_called_with(
                    ['./terraform', 'init', '-upgrade'],
                    stdout=provisioner.stdout,
                    stderr=provisioner.stderr)
                remove_calls = [call('provisioned.single'), call('provisioned.shard')]
                mock_remove.assert_has_calls(remove_calls)
                mock_open_file.assert_called_with('provisioned.single', 'w')
        self.reset_mock_objects()

    @patch('infrastructure_provisioning.subprocess.check_call')
    @patch('infrastructure_provisioning.os.remove')
    @patch('infrastructure_provisioning.os.chdir')
    @patch('infrastructure_provisioning.os.getcwd')
    @patch('infrastructure_provisioning.shutil.copyfile')
    def test_userexpand(self, mock_copyfile, mock_getcwd, mock_chdir, mock_remove, mock_check_call):
        """
        Test Provisioner.save_terraform_state with ~/.ssh/user_ssh_key.pem
        """
        config = copy.deepcopy(self.config)
        config['infrastructure_provisioning']['tfvars']['ssh_key_file'] = '~/.ssh/user_aws_key.pem'

        provisioned_files = ['provisioned.single', 'provisioned.shard']
        evg_data_dir = config['infrastructure_provisioning']['evergreen']['data_dir']
        terraform_dir = os.path.join(evg_data_dir, 'terraform')
        with patch('infrastructure_provisioning.glob.glob') as mock_glob:
            mock_open_file = mock_open()
            with patch('infrastructure_provisioning.open', mock_open_file, create=True):
                mock_glob.return_value = provisioned_files
                mock_getcwd.return_value = 'fake/path'
                provisioner = ip.Provisioner(config, provisioning_file=self.provision_log_path)
                provisioner.production = True
                provisioner.save_terraform_state()
                files_to_copy = ['terraform.tfstate', 'cluster.tf', 'security.tf', 'cluster.json']
                copyfile_calls = [
                    call(file_to_copy, os.path.join(terraform_dir, file_to_copy))
                    for file_to_copy in files_to_copy
                ]
                mock_copyfile.assert_has_calls(copyfile_calls)
        self.reset_mock_objects()

    def test_check_version(self):
        """
        Test infrastructure_provisioning.check_version (check a version file in evg_data_dir)
        """
        evg_data_dir = self.config['infrastructure_provisioning']['evergreen']['data_dir']

        # provisioned.single should always have an empty version number.
        self.assertFalse(ip.check_version(evg_data_dir + 'terraform/provisioned.single'))

        # provisioned.replica should have a version number equal to the current version in
        # infrastructure_provisioning.py.
        self.assertTrue(ip.check_version(evg_data_dir + 'terraform/provisioned.replica'))

        # provisioned.shard should have a version number one greater than the current version in
        # infrastructure_provisioning.py.
        self.assertFalse(ip.check_version(evg_data_dir + 'terraform/provisioned.shard'))

        # provisioned.initialsync-logkeeper should have a version number equal to the current
        # version in infrastructure_provisioning.py.
        self.assertTrue(
            ip.check_version(evg_data_dir + 'terraform/provisioned.initialsync-logkeeper'))

    @patch('infrastructure_provisioning.shutil.rmtree')
    @patch('infrastructure_provisioning.os.path.exists', return_value=False)
    @log_capture(level=logging.INFO)
    def test_rmtree_when_not_present(self, mock_rmtree, mock_exists, capture):
        """
        Test infrastructure_provisioning.rmtree_when_present fail path
        """
        # pylint: disable=no-self-use
        # self.assertLogs(logger='infrastructure_provisioning')
        ip.rmtree_when_present('')
        capture.check((
            'infrastructure_provisioning', 'INFO',
            u"[info     ] rmtree_when_present: No such path [infrastructure_provisioning] arg=u''"))

    @patch('infrastructure_provisioning.shutil.rmtree')
    @patch('infrastructure_provisioning.os.path.exists', return_value=True)
    @log_capture(level=logging.INFO)
    def test_rmtree_when_present(self, mock_rmtree, mock_exists, capture):
        """
        Test infrastructure_provisioning.rmtree_when_present success path
        """
        ip.rmtree_when_present('')
        capture.check()

    @patch('infrastructure_provisioning.os.path.exists', return_value=False)
    @log_capture()
    def test_rmtree_when_present_nopath(self, mock_exists, capture):
        """
        Test infrastructure_provisioning.rmtree_when_present path not found
        """
        ip.rmtree_when_present('')
        capture.check(
            ('infrastructure_provisioning', 'DEBUG',
             u"[debug    ] rmtree_when_present start      [infrastructure_provisioning] arg=u''"),
            ('infrastructure_provisioning', 'INFO',
             u"[info     ] rmtree_when_present: No such path [infrastructure_provisioning] arg=u''"
            )) # yapf: disable

    @patch('infrastructure_provisioning.shutil.rmtree', side_effect=OSError)
    @patch('infrastructure_provisioning.os.path.exists', return_value=True)
    @log_capture(level=logging.INFO)
    def test_rmtree_when_present_error(self, mock_rmtree, mock_exists, capture):
        """
        Test infrastructure_provisioning.rmtree_when_present unexpected error
        """
        with self.assertRaises(OSError):
            ip.rmtree_when_present('')
        capture.check()

    @log_capture()
    def test_print_terraform_errors(self, log_output):
        """
        Test infrastructure_provisioning.print_terraform_errors()
        """
        # pylint: disable=line-too-long
        provisioner = ip.Provisioner(self.config, provisioning_file=self.provision_log_path)
        provisioner.tf_log_path = FIXTURE_FILES.fixture_file_path('terraform.log.short')
        provisioner.print_terraform_errors()

        log_output.check(
            ('infrastructure_provisioning',
             'INFO',
             u"[info     ] Redirecting terraform output to file [infrastructure_provisioning] path=u'{}'".format(FIXTURE_FILES.fixture_file_path('terraform.stdout.log'))),
            ('infrastructure_provisioning',
             'ERROR',
             u'[error    ] 2018-03-05T15:45:36.018+0200 [DEBUG] plugin.terraform-provider-aws_v1.6.0_x4: <Response><Errors><Error><Code>InsufficientInstanceCapacity</Code><Message>Insufficient capacity.</Message></Error></Errors><RequestID>bd5b4071-755d-440e-8381-aa09bad52d69</RequestID></Response> [infrastructure_provisioning] '),
            ('infrastructure_provisioning',
             'ERROR',
             u'[error    ] 2018-03-05T15:45:36.914+0200 [DEBUG] plugin.terraform-provider-aws_v1.6.0_x4: <Response><Errors><Error><Code>RequestLimitExceeded</Code><Message>Request limit exceeded.</Message></Error></Errors><RequestID>6280e71d-9be4-442c-8ddf-00265efeafe6</RequestID></Response> [infrastructure_provisioning] '),
            ('infrastructure_provisioning',
             'ERROR',
             u"[error    ] 2018-03-05T15:48:36.336+0200 [DEBUG] plugin.terraform-provider-aws_v1.6.0_x4: <Response><Errors><Error><Code>InvalidRouteTableID.NotFound</Code><Message>The routeTable ID 'rtb-509f1528' does not exist</Message></Error></Errors><RequestID>54256eb4-d706-4084-86dc-b7f581006f9f</RequestID></Response> [infrastructure_provisioning] "),
            ('infrastructure_provisioning',
             'ERROR',
             u'[error    ] 2018-03-05T15:48:47.258+0200 [DEBUG] plugin.terraform-provider-aws_v1.6.0_x4: <Response><Errors><Error><Code>DependencyViolation</Code><Message>Network vpc-a9ed8bd0 has some mapped public address(es). Please unmap those public address(es) before detaching the gateway.</Message></Error></Errors><RequestID>cd102bc6-d598-4bae-80f5-25e62103f9a4</RequestID></Response> [infrastructure_provisioning] '),
            ('infrastructure_provisioning',
             'ERROR',
             u"[error    ] 2018-03-05T15:49:29.084+0200 [DEBUG] plugin.terraform-provider-aws_v1.6.0_x4: <Response><Errors><Error><Code>InvalidPlacementGroup.Unknown</Code><Message>The Placement Group 'shard-8665ea69-9e76-483a-937b-af68d41d54dd' is unknown.</Message></Error></Errors><RequestID>4264aef8-ae91-40f0-bc16-d914a8dc2cf8</RequestID></Response> [infrastructure_provisioning] "),
            ('infrastructure_provisioning',
             'ERROR',
             u"[error    ] For more info, see:            [infrastructure_provisioning] path=u'{}'".format(FIXTURE_FILES.fixture_file_path('terraform.log.short'))),
            ('infrastructure_provisioning',
             'ERROR',
             u'[error    ]                                [infrastructure_provisioning] '),
            ('infrastructure_provisioning',
             'ERROR',
             u"[error    ] For more info, see:            [infrastructure_provisioning] path=u'{}'".format(FIXTURE_FILES.fixture_file_path('terraform.stdout.log'))),
        ) # yapf: disable


if __name__ == '__main__':
    unittest.main()
