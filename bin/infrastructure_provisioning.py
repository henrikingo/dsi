#!/usr/bin/env python2.7
"""
Provision AWS resources using terraform
"""
import argparse
import glob
import os
import re
import shutil
import subprocess
import sys
import structlog

from common.log import setup_logging
from common.config import ConfigDict
from common.terraform_config import TerraformConfiguration
from common.terraform_output_parser import TerraformOutputParser
import common.utils
from infrastructure_teardown import destroy_resources

LOG = structlog.get_logger(__name__)

# Set terraform parallelism so it can create multiple resources
# The number determines the number it can create at a time together
TERRAFORM_PARALLELISM = 20
TF_LOG_PATH = "terraform.debug.log"
PROVISION_LOG_PATH = 'terraform.stdout.log'
CLUSTER_JSON = "cluster.json"

# Increase this to force a teardown of clusters whose evg_data_dir is from a previous version.
VERSION = "4"


def check_version(file_path):
    """True, if contents of file_path equals VERSION"""
    if os.path.isfile(file_path):
        with open(file_path) as file_handle:
            content = file_handle.read()
            LOG.debug("check_version", version=VERSION, file_path=file_path, contents=content)
            if content == VERSION:
                return True
    else:
        LOG.debug("check_version: No file at file_path", file_path=file_path)

    return False


def rmtree_when_present(tree_path):
    """Remove the given tree only if present"""
    LOG.debug("rmtree_when_present start", arg=tree_path)
    if os.path.exists(tree_path):
        shutil.rmtree(tree_path)
    else:
        LOG.info("rmtree_when_present: No such path", arg=tree_path)


# pylint: disable=too-many-instance-attributes
class Provisioner(object):
    """ Used to provision AWS resources """

    def __init__(self,
                 config,
                 log_file=TF_LOG_PATH,
                 provisioning_file=PROVISION_LOG_PATH,
                 verbose=False):
        self.config = config
        ssh_key_file = config['infrastructure_provisioning']['tfvars']['ssh_key_file']
        ssh_key_file = os.path.expanduser(ssh_key_file)
        self.ssh_key_file = ssh_key_file
        self.ssh_key_name = config['infrastructure_provisioning']['tfvars']['ssh_key_name']
        self.aws_access_key, self.aws_secret_key = common.utils.read_aws_credentials(config)
        self.cluster = config['infrastructure_provisioning']['tfvars'].get(
            'cluster_name', 'missing_cluster_name')
        self.reuse_cluster = config['infrastructure_provisioning']['evergreen'].get(
            'reuse_cluster', False)
        self.evg_data_dir = config['infrastructure_provisioning']['evergreen'].get('data_dir')
        self.existing = False
        self.var_file = None
        self.parallelism = '-parallelism=' + str(TERRAFORM_PARALLELISM)
        # infrastructure_teardown.py cannot import ConfigDict, so we use environment variable
        # for terraform location
        if "TERRAFORM" in os.environ:
            self.terraform = os.environ['TERRAFORM']
        else:
            self.terraform = './terraform'
        self.tf_log_path = TF_LOG_PATH

        os.environ['TF_LOG'] = 'DEBUG'
        os.environ['TF_LOG_PATH'] = TF_LOG_PATH

        self.dsi_dir = common.utils.get_dsi_path()
        self.bin_dir = common.utils.get_dsi_bin_dir()

        self.log_file = log_file
        self.verbose = verbose
        self.provisioning_file = provisioning_file

        # Counter-intuitively, _None_ has the following stream semantics.
        # "With the default settings of None, no redirection will occur; the child's file handles
        # will be inherited from the parent"
        # @see subprocess.Popen
        if self.verbose:
            self.stdout = self.stderr = None
        else:
            LOG.info("Redirecting terraform output to file", path=self.provisioning_file)
            self.stdout = self.stderr = open(self.provisioning_file, 'w')

    def setup_security_tf(self):
        """
        Generate the security.tf file
        """
        # Write security.tf.
        with open(os.path.join('security.tf'), 'w') as security:
            security.write('provider "aws" {\n')
            security.write('    access_key = "{0}"\n'.format(self.aws_access_key))
            security.write('    secret_key = "{0}"\n'.format(self.aws_secret_key))
            security.write('    region = "${var.region}"\n')
            security.write('    version = "{}"\n'.format(
                self.config['infrastructure_provisioning']['terraform']['aws_required_version']))
            security.write('}\n')
            security.write('variable "key_name" {\n')
            security.write('    default = "{0}"\n'.format(self.ssh_key_name))
            security.write('}\n')
            security.write('variable "key_file" {\n')
            security.write('    default = "{0}"\n'.format(self.ssh_key_file))
            security.write('}')

    def setup_terraform_tf(self):
        """
        Copy terraform tf files and remote-scripts to work directory
        """
        # Copy terraform files and remote-scripts to work directory
        directory = os.getcwd()
        cluster_path = os.path.join(self.dsi_dir, 'terraform', 'default')
        remote_scripts_path = os.path.join(self.dsi_dir, 'terraform', 'remote-scripts')
        LOG.debug('Cluster path is', path=cluster_path)
        for filename in glob.glob(os.path.join(cluster_path, '*')):
            shutil.copy(filename, directory)
            LOG.debug("Copied file to work directory.", source_path=filename, target_path=directory)
        remote_scripts_target = os.path.join(directory, 'remote-scripts')
        LOG.debug(
            "Create fresh directory and copy remote scripts.",
            source_path=remote_scripts_path,
            target_path=remote_scripts_target)
        rmtree_when_present(remote_scripts_target)
        os.mkdir(remote_scripts_target)
        for filename in glob.glob(os.path.join(remote_scripts_path, '*')):
            shutil.copy(filename, remote_scripts_target)
            LOG.debug(
                "Copied file to work directory.",
                source_path=filename,
                target_path=remote_scripts_target)

        # Copy modules
        modules_path = os.path.join(self.dsi_dir, 'terraform', 'modules')
        modules_target = os.path.join(directory, 'modules')
        rmtree_when_present(modules_target)
        shutil.copytree(modules_path, modules_target)
        LOG.debug(
            "Copied file to work directory.", source_path=modules_path, target_path=modules_target)

    def provision_resources(self):
        """
        Function used to actually provision the resources
        """
        if self.reuse_cluster:
            self.check_existing_state()
        self.setup_cluster()

    def teardown_old_cluster(self):
        """
        Force recreation of a new cluster by executing teardown in evg_data_dir and deleting state
        """
        try:
            # Need to unset the TERRAFORM environment variable since infrastructure_teardown.py
            # needs to use the correct version of terraform which is located in evg_data_dir.
            # The terraform version matches the version of the terraform state files located
            # in the same directory. The teardown script in evg_data_dir is used to ensure
            # the terraform in that directory is used.
            temp_environ = os.environ.copy()
            if 'TERRAFORM' in temp_environ:
                del temp_environ['TERRAFORM']

            teardown_py = os.path.join(self.evg_data_dir, 'terraform/infrastructure_teardown.py')
            if os.path.isfile(teardown_py):
                subprocess.check_call(
                    ['python', teardown_py],
                    env=temp_environ,
                    stdout=self.stdout,
                    stderr=self.stderr)
        except subprocess.CalledProcessError as exception:
            LOG.error(
                "Teardown of existing resources failed. Catching exception and continuing.",
                exception=str(exception))

        # Delete all state files so that this looks like a fresh evergreen runner
        rmtree_when_present(self.evg_data_dir)
        if os.path.isfile(CLUSTER_JSON):
            os.remove(CLUSTER_JSON)
        if os.path.isfile("terraform.tfstate"):
            os.remove("terraform.tfstate")

    def check_existing_state(self):
        """
        If running on evergreen, use an existing terraform state if it exists.
        Properly sets up the environment on Evergreen to use the existing
        state files.
        """
        if os.path.isdir(self.evg_data_dir) and self.cluster == 'initialsync-logkeeper':
            LOG.info(
                "Force re-creation of instances by executing teardown now.", cluster=self.cluster)
            self.teardown_old_cluster()

        tfstate_path = os.path.join(self.evg_data_dir, 'terraform/terraform.tfstate')
        provision_cluster_path = os.path.join(self.evg_data_dir,
                                              'terraform/provisioned.' + self.cluster)
        if os.path.isfile(tfstate_path):
            if check_version(provision_cluster_path):
                self.existing = True
                LOG.info(
                    "Retrieving terraform state for existing EC2 resources.", path=tfstate_path)
                shutil.copyfile(tfstate_path, "./terraform.tfstate")

                LOG.info("Retrieving variables for existing EC2 resources.", path=CLUSTER_JSON)
                from_file = os.path.join(self.evg_data_dir, 'terraform', CLUSTER_JSON)
                shutil.copyfile(from_file, CLUSTER_JSON)
            else:
                LOG.info(
                    "Existing EC2 resources found, but state files are wrong version. "
                    "Force re-creation of cluster now...",
                    path=provision_cluster_path)
                self.teardown_old_cluster()
                self.existing = False

        else:
            self.existing = False
            LOG.info("No existing EC2 resources found.", path=tfstate_path)

    def setup_evg_dir(self):
        """
        Sets up the Evergreen data directories and creates them if they do not exist.
        Copies over the terraform modules along with the teardown script.
        data directory.
        """
        if not os.path.isdir(self.evg_data_dir):
            LOG.info(
                "Copying terraform binary to durable data directory on Evergreen host.",
                target_path=self.evg_data_dir)
            os.makedirs(self.evg_data_dir)
            # While everything else is inside the work directory, setup-dsi-env.sh still downloads
            # terraform into a directory that is parallel to work, not inside it.
            # Also note that the below is the directory called "terraform". (Yes, it contains a
            # binary called "terraform".)
            shutil.copytree("../terraform", os.path.join(self.evg_data_dir, "terraform"))
            shutil.copytree("./modules", os.path.join(self.evg_data_dir, "terraform/modules"))

            source_path = os.path.join(self.bin_dir, 'infrastructure_teardown.py')
            target_path = os.path.join(self.evg_data_dir, 'terraform/infrastructure_teardown.py')
            LOG.info(
                "Copying infrastructure_teardown.py to Evergreen host.",
                source_path=source_path,
                target_path=target_path)
            shutil.copyfile(source_path, target_path)
            os.chmod(os.path.join(self.evg_data_dir, 'terraform/infrastructure_teardown.py'), 0755)

        LOG.info(
            "Contents of Evergreen durable data directory.",
            path=self.evg_data_dir,
            contents=os.listdir(self.evg_data_dir))
        LOG.info(
            "Contents of terraform/ sub directory.",
            path=os.path.join(self.evg_data_dir, "terraform"),
            contents=os.listdir(os.path.join(self.evg_data_dir, "terraform")))

    def setup_cluster(self):
        """
        Runs terraform to provision the cluster
        """
        # Create and copy needed security.tf and terraform.tf files into current work directory
        self.setup_security_tf()
        self.setup_terraform_tf()
        if self.reuse_cluster:
            self.setup_evg_dir()
        LOG.info('terraform: init')
        subprocess.check_call(
            [self.terraform, 'init', '-upgrade'], stdout=self.stdout, stderr=self.stderr)
        tf_config = TerraformConfiguration(self.config)
        tf_config.to_json(file_name=CLUSTER_JSON)  # pylint: disable=no-member
        self.var_file = '-var-file={}'.format(CLUSTER_JSON)
        if self.existing:
            LOG.info('Reusing AWS cluster.', cluster=self.cluster)
        else:
            LOG.info('Creating AWS cluster.', cluster=self.cluster)
        LOG.info('terraform: apply')
        terraform_command = [self.terraform, 'apply', self.var_file, self.parallelism]
        # Disk warmup for initialsync-logkeeper takes about 4 hours. This will save
        # about $12 by delaying deployment of the two other nodes.
        if not self.existing and self.cluster == 'initialsync-logkeeper':
            terraform_command.extend(
                ['-var="mongod_ebs_instance_count=0"', '-var="workload_instance_count=0"'])
        try:
            subprocess.check_call(terraform_command, stdout=self.stdout, stderr=self.stderr)
            if not self.existing and self.cluster == 'initialsync-logkeeper':
                subprocess.check_call(
                    [self.terraform, 'apply', self.var_file, self.parallelism],
                    stdout=self.stdout,
                    stderr=self.stderr)
            LOG.info('terraform: refresh')
            subprocess.check_call(
                [self.terraform, 'refresh', self.var_file], stdout=self.stdout, stderr=self.stderr)
            LOG.info('terraform: plan')
            subprocess.check_call(
                [self.terraform, 'plan', '-detailed-exitcode', self.var_file],
                stdout=self.stdout,
                stderr=self.stderr)
            LOG.info('terraform: output')
            terraform_output = run_and_save_output([self.terraform, 'output'])
            LOG.debug(terraform_output)
            tf_parser = TerraformOutputParser(terraform_output=terraform_output)
            tf_parser.write_output_files()

            with open('infrastructure_provisioning.out.yml', 'r') as provisioning_out_yaml:
                LOG.info('Contents of infrastructure_provisioning.out.yml:')
                LOG.info(provisioning_out_yaml.read())
            LOG.info("EC2 resources provisioned/updated successfully.")
            if self.reuse_cluster:
                self.save_terraform_state()
        except Exception as exception:
            LOG.info("Failed to provision EC2 resources.")
            if self.stderr is not None:
                self.stderr.close()
            self.print_terraform_errors()
            LOG.info("Releasing any EC2 resources that did deploy.")
            destroy_resources()
            rmtree_when_present(self.evg_data_dir)
            raise exception

    def save_terraform_state(self):
        """
        Saved the terraform state to the Evergreen data directory and also
        copy over the ssh key.
        """
        LOG.info("Will now save terraform state needed for "
                 "teardown when triggered by the Evergreen runner.")
        terraform_dir = os.path.join(self.evg_data_dir, 'terraform')
        files_to_copy = ['terraform.tfstate', 'cluster.tf', 'security.tf', CLUSTER_JSON]
        LOG.info('Copying files.', files=files_to_copy)
        for to_copy in files_to_copy:
            shutil.copyfile(to_copy, os.path.join(terraform_dir, to_copy))
        # If ssh_key_file is a relative path, copy it too
        # Important: If you provide an absolute path in the configuration, make sure it doesn't
        # point to a temporary path! (/tmp, or evergreen runner work dir)
        if not os.path.isabs(self.ssh_key_file):
            source_path = self.ssh_key_file
            target_path = os.path.join(terraform_dir, self.ssh_key_file)
            LOG.info('Copying:', source_path=source_path, target_path=target_path)
            shutil.copyfile(source_path, target_path)

        previous_working_directory = os.getcwd()
        os.chdir(terraform_dir)
        LOG.info('terraform: init in Evergreen data dir.', path=terraform_dir)
        subprocess.check_call(
            ['./terraform', 'init', '-upgrade'], stdout=self.stdout, stderr=self.stderr)
        for file_path in glob.glob('provisioned.*'):
            os.remove(file_path)
        with open('provisioned.' + self.cluster, 'w') as file_handle:
            file_handle.write(VERSION)
            LOG.info(
                'Created version file to denote the version of terraform state files.',
                path='provisioned.' + self.cluster,
                version=VERSION)
        os.chdir(previous_working_directory)
        LOG.info("EC2 provisioning state saved on Evergreen host.")

    def print_terraform_errors(self):
        """
        Grep and print errors from terraform.log and provisioning.log.

        Since Summer 2017, Terraform usually fails to print the actual EC2 error that caused a
        deployment to fail, and instead just keeps spinning until you get a timeout error instead.
        The real error, such as InsufficientInstanceCapacity, is however logged in our very verbose
        terraform.log file. As a convenience to the user, we will find and print errors from it.
        See PERF-1095 for more info.
        """
        # pylint: disable=too-many-nested-blocks
        strings_to_grep = set(["<Response><Errors><Error>"])
        strings_to_ignore = set(["The specified rule does not exist in this security group."])
        seen_errors = set()

        # Print errors from terraform.log.
        for line in open(self.tf_log_path):
            for to_grep in strings_to_grep:
                if to_grep in line:
                    print_it = True
                    for to_ignore in strings_to_ignore:
                        if to_ignore in line:
                            print_it = False

                    if print_it:
                        line = line.strip()
                        # Terraform is very persistent, so it will often retry a non-recoverable
                        # error multiple times, and the verbose log is then full with the same
                        # error. We print each kind of error only once. So we need to keep track
                        # of them.
                        result = re.search(r'\<Code\>(.+)\</Code\>', line)
                        if result:
                            error_code = result.group(1)
                            if error_code not in seen_errors:
                                seen_errors.add(error_code)
                                LOG.error(line)
                        else:
                            LOG.error(line)

        if seen_errors:
            LOG.error("For more info, see:", path=self.tf_log_path)

        # Print tail of provisioning.log.
        if os.path.exists(self.provisioning_file):
            LOG.error(subprocess.check_output(["tail", "-n 100", self.provisioning_file]))
            LOG.error("For more info, see:", path=self.provisioning_file)


# pylint: enable=too-many-instance-attributes


def run_and_save_output(command):
    """
    Used to replicate the tee command. Sends the output from the command
    to both the log_file and to stdout.
    """
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    # This ensures that as subprocess runs the command, the output is caught in real time
    # and is not buffered by subprocess.
    output = ''
    for line in iter(process.stdout.readline, ""):
        sys.stdout.write(line)
        output = output + line
    process.communicate()
    if process.returncode != 0:
        raise subprocess.CalledProcessError(process.returncode, command, output=output)
    return output


def parse_command_line():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Provision EC2 instances on AWS using terraform.')
    parser.add_argument('--log-file', help='path to log file')
    parser.add_argument('-d', '--debug', action='store_true', help='enable debug output')
    args = parser.parse_args()
    return args


def main():
    """ Main function """
    args = parse_command_line()
    setup_logging(args.debug, args.log_file)
    config = ConfigDict('infrastructure_provisioning')
    config.load()
    provisioner = Provisioner(config, verbose=args.debug)
    provisioner.provision_resources()


if __name__ == '__main__':
    main()
