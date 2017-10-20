# pylint: disable=protected-access
"""test file for terraform_env"""

from __future__ import print_function
import unittest
import os
import yaml

from bin.common import terraform_output_parser as tf_output

DIR = os.path.dirname(os.path.abspath(__file__))


class TestTerraformOutputParser(unittest.TestCase):
    """To test terraform configuration"""

    def setUp(self):
        """Setup so config dict works properly"""
        self.old_dir = os.getcwd()  # Save the old path to restore Note
        # that this chdir only works without breaking relative imports
        # because it's at the same directory depth
        os.chdir(os.path.dirname(os.path.abspath(__file__)) + '/../../docs/config-specs/')

    def tearDown(self):
        """Restore working directory"""
        os.chdir(self.old_dir)

    def test_single_cluster_value(self):
        """Test parsing single cluster value is correct."""
        output = tf_output.TerraformOutputParser(
            input_file=os.path.join(DIR, "artifacts/terraform_single_cluster_output.txt"))

        print(output._ips)

        self.assertEqual(["52.32.13.97"], output._ips["public_ip_mc"])
        self.assertEqual(["52.26.153.91"], output._ips["public_member_ip"])
        self.assertEqual(["10.2.0.100"], output._ips["private_member_ip"])

    def test_replica_ebs_cluster_value(self):
        """Test parsing replica_ebs cluster."""
        output = tf_output.TerraformOutputParser(
            input_file=os.path.join(DIR, "artifacts/terraform_replica_with_ebs_output.txt"))

        print(output._ips)

        self.assertEqual(["52.33.30.1"], output._ips["public_ip_mc"])
        self.assertEqual("52.41.40.0", output._ips["public_member_ip"][0])
        self.assertEqual("52.37.52.162", output._ips["public_member_ip"][1])
        self.assertEqual("52.25.102.16", output._ips["public_member_ip"][2])
        self.assertEqual("52.25.102.17", output._ips["public_member_ip"][3])
        self.assertEqual("10.2.0.100", output._ips["private_member_ip"][0])

    def test_shard_cluster_value(self):
        """Test parsing shard cluster value is correct."""
        output = tf_output.TerraformOutputParser(
            input_file=os.path.join(DIR, "artifacts/terraform_shard_cluster_output.txt"))

        print(output._ips)

        # Test ip address is correct for different members
        self.assertEqual(["52.11.198.150"], output._ips["public_ip_mc"])
        self.assertEqual("52.26.155.122", output._ips["public_member_ip"][0])
        self.assertEqual("52.38.108.78", output._ips["public_member_ip"][4])
        self.assertEqual("10.2.0.100", output._ips["private_member_ip"][0])
        self.assertEqual("10.2.0.106", output._ips["private_member_ip"][6])

        self.assertEqual("52.38.116.84", output._ips["public_config_ip"][0])
        self.assertEqual("52.27.136.80", output._ips["public_config_ip"][1])
        self.assertEqual("10.2.0.81", output._ips["private_config_ip"][0])
        self.assertEqual("10.2.0.83", output._ips["private_config_ip"][2])

        # Test total monogod count
        self.assertEqual(9, len(output._ips["public_member_ip"]))
        self.assertEqual(9, len(output._ips["private_member_ip"]))

        # Test config_server count
        self.assertEqual(3, len(output._ips["public_config_ip"]))
        self.assertEqual(3, len(output._ips["private_config_ip"]))

    def test_single_cluster_yml(self):
        """Test parsing single cluster YML file is correct."""
        output = tf_output.TerraformOutputParser(
            input_file=DIR + "/artifacts/terraform_single_cluster_output.txt")
        output._generate_output()
        reference = {}
        with open(DIR + "/artifacts/terraform_single.out.yml") as fread:
            reference = yaml.safe_load(fread)

        print(reference['out'])
        print(output.config_obj['infrastructure_provisioning']['out'])
        self.assertEqual(output.config_obj['infrastructure_provisioning']['out'].as_dict(),
                         reference['out'])

    def test_shard_cluster_yml(self):
        """Test parsing single cluster YML file is correct."""
        output = tf_output.TerraformOutputParser(
            input_file=DIR + "/artifacts/terraform_shard_cluster_output.txt")

        output._generate_output()
        reference = {}
        with open(DIR + "/artifacts/terraform_shard.out.yml") as fread:
            reference = yaml.safe_load(fread)

        print(reference['out'])
        print(output.config_obj['infrastructure_provisioning']['out'])
        self.assertEqual(output.config_obj['infrastructure_provisioning']['out'].as_dict(),
                         reference['out'])
