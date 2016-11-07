# pylint: disable=protected-access

"""test file for terraform_env"""

from __future__ import print_function
import unittest
import os

from bin.common import terraform_output_parser as tf_output  # pylint: disable=E0401

DIR = os.path.dirname(os.path.abspath(__file__))


class TestTerraformOutputParser(unittest.TestCase):
    """To test terraform configuration"""

    def test_single_cluster_value(self):
        """Test parsing single cluster value is correct."""
        output = tf_output.TerraformOutputParser(
            input_file=DIR+"/artifacts/terraform_single_cluster_output.txt")

        print(output._generate_yml())
        self.assertEqual(["52.32.13.97"], output._ips["public_ip_mc"])
        self.assertEqual(["52.26.153.91"], output._ips["public_member_ip"])
        self.assertEqual(["10.2.0.100"], output._ips["private_member_ip"])

    def test_replica_ebs_cluster_value(self):
        """Test parsing replica_ebs cluster."""
        output = tf_output.TerraformOutputParser(
            input_file=DIR+"/artifacts/terraform_replica_with_ebs_output.txt")

        print(output._generate_yml())
        self.assertEqual(["52.33.30.1"], output._ips["public_ip_mc"])
        self.assertEqual("52.41.40.0", output._ips["public_member_ip"][0])
        self.assertEqual("10.2.0.100", output._ips["private_member_ip"][0])
        self.assertEqual("10.2.0.200", output._ips["private_mongod_ebs_ip"][0])
        self.assertEqual("52.25.102.16", output._ips["public_mongod_ebs_ip"][0])

    def test_shard_cluster_value(self):
        """Test parsing shard cluster value is correct."""
        output = tf_output.TerraformOutputParser(
            input_file=DIR+"/artifacts/terraform_shard_cluster_output.txt")

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
            input_file=DIR+"/artifacts/terraform_single_cluster_output.txt")

        print(output._generate_yml())
        with open(DIR+"/artifacts/terraform_single.out.yml") as fread:
            lines = fread.readlines()
            print(''.join(lines))
            self.assertEqual(''.join(lines), output._generate_yml())

    def test_replica_ebs_cluster_yml(self):
        """Test replica_ebs YML out file is correct."""
        output = tf_output.TerraformOutputParser(
            input_file=DIR+"/artifacts/terraform_replica_with_ebs_output.txt")

        print(output._generate_yml())
        with open(DIR+"/artifacts/terraform_replica_with_ebs.out.yml") as fread:
            lines = fread.readlines()
            print(''.join(lines))
            self.assertEqual(''.join(lines), output._generate_yml())

    def test_shard_cluster_yml(self):
        """Test parsing single cluster YML file is correct."""
        output = tf_output.TerraformOutputParser(
            input_file=DIR+"/artifacts/terraform_shard_cluster_output.txt")

        print(output._generate_yml())
        with open(DIR+"/artifacts/terraform_shard.out.yml") as fread:
            lines = fread.readlines()
            print(''.join(lines))
            self.assertEqual(''.join(lines), output._generate_yml())
