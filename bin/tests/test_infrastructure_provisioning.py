"""
Unit test for infrastructure_provisioning.py
"""

from functools import partial
import logging
import os
import unittest
from subprocess import CalledProcessError
from mock import patch, call, mock_open
from testfixtures import LogCapture

from infrastructure_provisioning import Provisioner

#pylint: disable=too-many-locals
#pylint: disable=too-many-arguments


class TestInfrastructureProvisioning(unittest.TestCase):
    """ Test suite for infrastructure_provisioning.py """

    def setUp(self):
        self.config_patcher = patch('common.config.ConfigDict')
        self.mock_config = self.config_patcher.start()
        self.os_environ_patcher = patch('infrastructure_provisioning.os.environ')
        self.mock_environ = self.os_environ_patcher.start()
        self.reset_mock_objects()
        self.config = {
            'bootstrap': {
                'infrastructure_provisioning': 'single'
            },
            'infrastructure_provisioning': {
                'tfvars': {
                    'cluster_name': 'single',
                    'ssh_key_file': 'aws_ssh_key.pem'
                },
                'evergreen': {
                    'data_dir': 'test/evergreen/data_dir'
                }
            }
        }

    def reset_mock_objects(self):
        """
        Used to reset the test config dict, environment variables,
        and mock objects.
        """
        self.os_environ = {
            'TERRAFORM': 'test/path/terraform',
            'DSI_PATH': 'test/path/dsi'
        }
        #pylint: disable=no-member
        self.mock_environ.__getitem__.side_effect = self.os_environ.__getitem__
        self.mock_environ.__contains__.side_effect = self.os_environ.__contains__
        self.mock_environ.__delitem__.side_effect = self.os_environ.__delitem__
        #pylint: enable=no-member

    def mock_get_config(self, key, default=None):
        """ Used to mock ConfigDict.get since the entire object is mocked in tests """
        if key in self.config:
            return self.config[key]
        else:
            return default

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
        """ Test Provisioner.__init__ """
        self.config['bootstrap']['infrastructure_provisioning'] = 'single'
        # Check when TERRAFORM is an environment variable
        provisioner = Provisioner(self.config)
        self.assertEqual(provisioner.cluster, 'single')
        self.assertFalse(provisioner.reuse_cluster)
        self.assertEqual(provisioner.dsi_dir, 'test/path/dsi')
        self.assertFalse(provisioner.existing)
        self.assertEqual(provisioner.parallelism, '-parallelism=20')
        self.assertEqual(provisioner.terraform, 'test/path/terraform')

        # Check when TERRAFORM is not environment variable
        os_environ_missing_terraform = self.os_environ.copy()
        del os_environ_missing_terraform['TERRAFORM']
        self.mock_environ.__getitem__.side_effect = os_environ_missing_terraform.__getitem__
        self.mock_environ.__contains__.side_effect = os_environ_missing_terraform.__contains__
        provisioner_missing_terraform = Provisioner(self.config)
        self.assertEqual(provisioner_missing_terraform.cluster, 'single')
        self.assertFalse(provisioner_missing_terraform.reuse_cluster)
        self.assertEqual(provisioner_missing_terraform.dsi_dir, 'test/path/dsi')
        self.assertFalse(provisioner_missing_terraform.existing)
        self.assertEqual(provisioner_missing_terraform.parallelism, '-parallelism=20')
        self.assertEqual(provisioner_missing_terraform.terraform, './terraform')
        self.reset_mock_objects()

    @patch('infrastructure_provisioning.Provisioner.setup_evg_dir')
    @patch('infrastructure_provisioning.shutil')
    @patch('infrastructure_provisioning.subprocess.check_call')
    @patch('infrastructure_provisioning.os.path.isdir')
    def test_check_existing_state(self, mock_isdir, mock_check_call,
                                  mock_shutil, mock_setup_evg_dir):
        """ Test Provisioner.existing_state """
        self.config['infrastructure_provisioning']['tfvars']['cluster_name'] = \
            'initialsync-logkeeper'
        evg_data_dir = self.config['infrastructure_provisioning']['evergreen']['data_dir']
        mock_isdir.side_effect = lambda evg_dir: evg_dir == evg_data_dir
        # Run check_existing_state when existing state exists
        with patch('infrastructure_provisioning.os.path.isfile') as mock_isfile:
            expected_command = ['python', evg_data_dir + '/terraform/infrastructure_teardown.py']
            mock_check_call.side_effect = partial(self.check_subprocess_call, expected_command)
            mock_isfile.return_value = True
            provisioner = Provisioner(self.config)
            self.assertEqual(provisioner.evg_data_dir, evg_data_dir)
            provisioner.check_existing_state()
            mock_shutil.rmtree.assert_called_with(evg_data_dir)
            self.assertTrue(mock_setup_evg_dir.called)
            isfile_calls = [
                call(evg_data_dir + '/terraform/terraform.tfstate'),
                call(evg_data_dir + '/terraform/provisioned.initialsync-logkeeper')
            ]
            mock_isfile.assert_has_calls(isfile_calls)
            self.assertTrue(provisioner.existing)

        # Run check_existing_state when no existing state exists
        with patch('infrastructure_provisioning.os.path.isfile') as mock_isfile:
            expected_command = ['test/evergreen/data_dir/terraform/infrastructure_teardown.sh']
            mock_check_call.side_effect = partial(self.check_subprocess_call, expected_command)
            mock_isfile.return_value = False
            provisioner = Provisioner(self.config)
            provisioner.check_existing_state()
            mock_shutil.rmtree.assert_called_with(evg_data_dir)
            self.assertTrue(mock_setup_evg_dir.called)
            isfile_calls = [call(evg_data_dir + '/terraform/terraform.tfstate')]
            mock_isfile.assert_has_calls(isfile_calls)
            self.assertFalse(provisioner.existing)
        self.reset_mock_objects()

    @patch('infrastructure_provisioning.Provisioner.setup_evg_dir')
    @patch('infrastructure_provisioning.shutil')
    @patch('infrastructure_provisioning.subprocess.check_call')
    @patch('infrastructure_provisioning.os.path.isdir')
    #pylint: disable=invalid-name
    def test_check_existing_state_teardown_fails(self, mock_isdir, mock_check_call, mock_shutil,
                                                 mock_setup_evg_dir):
        """Test Provisioner.existing_state when teardown fails. The code should catch the exception,
        and continue execution."""

        self.config['infrastructure_provisioning']['tfvars']['cluster_name'] = \
            'initialsync-logkeeper'
        evg_data_dir = self.config['infrastructure_provisioning']['evergreen']['data_dir']
        mock_isdir.side_effect = lambda evg_dir: evg_dir == evg_data_dir
        with patch('infrastructure_provisioning.os.path.isfile') as mock_isfile:
            mock_check_call.side_effect = CalledProcessError(1, ['cmd'])
            mock_isfile.return_value = True
            provisioner = Provisioner(self.config)
            self.assertEqual(provisioner.evg_data_dir, evg_data_dir)
            with LogCapture(level=logging.ERROR) as error:
                provisioner.check_existing_state()
                error.check(
                    ('infrastructure_provisioning', 'ERROR',
                     'Teardown of existing resources failed. Catching exception and continuing'),
                    ('infrastructure_provisioning', 'ERROR', str(CalledProcessError(1, ['cmd']))))
            mock_shutil.rmtree.assert_called_with(evg_data_dir)
            self.assertTrue(mock_setup_evg_dir.called)
            isfile_calls = [
                call(evg_data_dir + '/terraform/terraform.tfstate'),
                call(evg_data_dir + '/terraform/provisioned.initialsync-logkeeper')
            ]
            # This call to check_existing_state should follow the same path as the working case,
            # through the sub_process.check_call. As such, it should have the same isfile calls as
            # that case.
            mock_isfile.assert_has_calls(isfile_calls)
            self.assertTrue(provisioner.existing)

        self.reset_mock_objects()

    @patch('infrastructure_provisioning.shutil')
    @patch('infrastructure_provisioning.os.listdir')
    @patch('infrastructure_provisioning.os.path.isdir')
    @patch('infrastructure_provisioning.os.chmod')
    def test_setup_evg_dir(self, mock_chmod, mock_isdir, mock_listdir, mock_shutil):
        """ Test Provisioner.setup_evg_dir """
        evg_data_dir = self.config['infrastructure_provisioning']['evergreen']['data_dir']
        # Test when evergreen data directories do not exist
        with patch('infrastructure_provisioning.os.makedirs') as mock_makedirs:
            mock_isdir.return_value = False
            provisioner = Provisioner(self.config)
            provisioner.bin_dir = 'test/bin'
            provisioner.setup_evg_dir()
            mock_makedirs.assert_called_with(evg_data_dir)
            copytree_calls = [call('../terraform', evg_data_dir + '/terraform'),
                              call('./modules', evg_data_dir + '/terraform/modules')]
            mock_shutil.copytree.assert_has_calls(copytree_calls)
            copyfile_calls = [call(provisioner.bin_dir + '/infrastructure_teardown.sh',
                                   evg_data_dir + '/terraform/infrastructure_teardown.sh'),
                              call(provisioner.bin_dir + '/infrastructure_teardown.py',
                                   evg_data_dir + '/terraform/infrastructure_teardown.py')]
            mock_shutil.copyfile.assert_has_calls(copyfile_calls)
            listdir_calls = [call(evg_data_dir), call(os.path.join(evg_data_dir, 'terraform'))]
            # any_order is set to True because when running nosetests, listdir has extra
            # __str__() calls due to logging
            mock_listdir.assert_has_calls(listdir_calls, any_order=True)

        # Test when evergreen data directories do exist
        with patch('infrastructure_provisioning.os.makedirs') as mock_makedirs:
            mock_isdir.return_value = True
            provisioner = Provisioner(self.config)
            provisioner.bin_dir = 'test/bin'
            provisioner.setup_evg_dir()
            self.assertFalse(mock_makedirs.called)
        self.reset_mock_objects()

    @patch('infrastructure_provisioning.Provisioner.save_terraform_state')
    @patch('infrastructure_provisioning.TerraformOutputParser')
    @patch('infrastructure_provisioning.TerraformConfiguration')
    @patch('infrastructure_provisioning.run_and_save_output')
    @patch('infrastructure_provisioning.subprocess')
    def test_setup_cluster(self, mock_subprocess, mock_save_output, mock_terraform_configuration,
                           mock_terraform_output_parser, mock_save_terraform_state):
        """ Test Provisioner.setup_cluster """
        # NOTE: This tests the majority of the functionality of the infrastructure_provisioning.py
        # mock.mock_open is needed to effectively mock out the open() function in python
        mock_open_file = mock_open()
        with patch('infrastructure_provisioning.open', mock_open_file, create=True):
            provisioner = Provisioner(self.config)
            provisioner.cluster = 'initialsync-logkeeper'
            provisioner.reuse_cluster = True
            provisioner.setup_cluster()
            #pylint: disable=line-too-long
            mock_terraform_configuration.return_value.to_json.assert_called_with(file_name='cluster.json')
            #pylint: enable=line-too-long
            # __enter__ and __exit__ are checked to see if the files were opened
            # as context managers.
            open_file_calls = [call('infrastructure_provisioning.out.yml', 'r'),
                               call().read()]
            mock_open_file.assert_has_calls(open_file_calls, any_order=True)
            # If the cluster is initialsync-logkeeper, then terraform should be run twice
            terraform = self.os_environ['TERRAFORM']
            check_call_calls = [call([terraform, 'init', '-upgrade']),
                                call([terraform, 'apply', '-var-file=cluster.json',
                                      provisioner.parallelism, '-var="mongod_ebs_instance_count=0"',
                                      '-var="workload_instance_count=0"']),
                                call([terraform, 'apply', '-var-file=cluster.json',
                                      provisioner.parallelism]),
                                call([terraform, 'refresh', '-var-file=cluster.json']),
                                call([terraform, 'plan', '-detailed-exitcode',
                                      '-var-file=cluster.json'])]
            mock_subprocess.check_call.assert_has_calls(check_call_calls)
            mock_save_output.assert_called_with([terraform, 'output'])
            self.assertTrue(mock_terraform_output_parser.return_value.write_output_files.called)
            self.assertTrue(mock_save_terraform_state.called)
        self.reset_mock_objects()

    @patch('infrastructure_provisioning.shutil.rmtree')
    @patch('infrastructure_provisioning.Provisioner.save_terraform_state')
    @patch('infrastructure_provisioning.TerraformOutputParser')
    @patch('infrastructure_provisioning.TerraformConfiguration')
    @patch('infrastructure_provisioning.subprocess')
    def test_setup_cluster_failure(self, mock_subprocess, mock_terraform_configuration,
                                   mock_terraform_output_parser, mock_save_terraform_state,
                                   mock_rmtree):
        """Test Provisioner.setup_cluster when an error happens. Ensure that the cluster is torn
        down

        """
        # NOTE: This tests the majority of the functionality of the infrastructure_provisioning.py
        mock_open_file = mock_open()
        with patch('infrastructure_provisioning.open', mock_open_file, create=True):
            with patch('infrastructure_provisioning.destroy_resources') as mock_destroy:
                provisioner = Provisioner(self.config)
                provisioner.reuse_cluster = True
                mock_subprocess.check_call.side_effect = [1, CalledProcessError(1, ['cmd'])]
                with self.assertRaises(CalledProcessError):
                    provisioner.setup_cluster()
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
    def test_save_terraform_state(self, mock_copyfile, mock_getcwd,
                                  mock_chdir, mock_remove, mock_check_call):
        """ Test Provisioner.save_terraform_state """
        provisioned_files = ['provisioned.single', 'provisioned.shard']
        evg_data_dir = self.config['infrastructure_provisioning']['evergreen']['data_dir']
        terraform_dir = os.path.join(evg_data_dir, 'terraform')
        with patch('infrastructure_provisioning.glob.glob') as mock_glob:
            mock_open_file = mock_open()
            with patch('infrastructure_provisioning.open', mock_open_file, create=True):
                mock_glob.return_value = provisioned_files
                mock_getcwd.return_value = 'fake/path'
                provisioner = Provisioner(self.config)
                provisioner.production = True
                provisioner.save_terraform_state()
                files_to_copy = ['terraform.tfstate', 'cluster.tf', 'terraform.tfvars',
                                 'security.tf', 'cluster.json', 'aws_ssh_key.pem']
                copyfile_calls = [call(file_to_copy,
                                       os.path.join(terraform_dir, file_to_copy))
                                  for file_to_copy in files_to_copy]
                mock_copyfile.assert_has_calls(copyfile_calls)
                chdir_calls = [call(terraform_dir), call(mock_getcwd.return_value)]
                mock_chdir.assert_has_calls(chdir_calls)
                mock_check_call.assert_called_with(['./terraform', 'init', '-upgrade'])
                remove_calls = [call('provisioned.single'), call('provisioned.shard')]
                mock_remove.assert_has_calls(remove_calls)
                mock_open_file.assert_called_with('provisioned.single', 'w+')
        self.reset_mock_objects()

    def tearDown(self):
        self.config_patcher.stop()
        self.os_environ_patcher.stop()


if __name__ == '__main__':
    unittest.main()
