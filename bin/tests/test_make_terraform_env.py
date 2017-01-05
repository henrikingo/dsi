"""test file for terraform_env"""

from __future__ import print_function
import unittest
import datetime
import os
from mock import patch

from common import terraform_config  # pylint: disable=import-error


class TestTerraformConfiguration(unittest.TestCase):
    """To test terraform configuration class."""

    def _test_configuration(self, tf_config, expected_output_string):
        json_string = tf_config.to_json(compact=True)
        self.assertEqual(json_string, expected_output_string)

    @patch('common.terraform_config.generate_runner')
    def test_default(self, mock_generate_runner):
        """Test default terraform configuration, that is to update expire-on only."""
        mock_generate_runner.return_value = '111.111.111.111'
        tf_config = terraform_config.TerraformConfiguration(
            use_config=False,
            now=datetime.datetime(2016, 5, 25, 7, 11, 49, 131998))
        json_string = tf_config.to_json(compact=True)

        self.assertEqual(json_string,
                         '{"expire_on":"2016-5-27","runner":"111.111.111.111","status":"running"}')

    @patch('common.terraform_config.generate_runner')
    def test_mongod_instance(self, mock_generate_runner):
        """Test mongod instance parameters."""
        mock_generate_runner.return_value = '111.111.111.111'
        tf_config = terraform_config.TerraformConfiguration(
            topology="test-cluster",
            use_config=False,
            now=datetime.datetime(2016, 5, 25, 7, 11, 49, 131998))
        tf_config.define_instance(None, "mongod", 10, "c3.8xlarge")
        self._test_configuration(tf_config,
                                 '{"expire_on":"2016-5-27",'
                                 '"mongod_instance_count":10,'
                                 '"mongod_instance_placement_group":"yes",'
                                 '"mongod_instance_type":"c3.8xlarge",'
                                 '"runner":"111.111.111.111",'
                                 '"status":"running",'
                                 '"topology":"test-cluster"}')

    @patch('common.terraform_config.generate_runner')
    def test_large_cluster(self, mock_generate_runner):
        """Test cluster with mixed instances."""
        mock_generate_runner.return_value = '111.111.111.111'
        tf_config = terraform_config.TerraformConfiguration(
            topology="test-cluster",
            use_config=False,
            now=datetime.datetime(2016, 5, 25, 7, 11, 49, 131998))

        tf_config.define_instance(None, "mongos", 1, "m3.2xlarge")
        tf_config.define_instance(None, "mongod", 10, "c3.2xlarge")
        tf_config.define_instance(None, "configsvr", 3, "m3.xlarge")
        self._test_configuration(tf_config,
                                 '{"configsvr_instance_count":3,'
                                 '"configsvr_instance_placement_group":"no",'
                                 '"configsvr_instance_type":"m3.xlarge",'
                                 '"expire_on":"2016-5-27",'
                                 '"mongod_instance_count":10,'
                                 '"mongod_instance_placement_group":"yes",'
                                 '"mongod_instance_type":"c3.2xlarge",'
                                 '"mongos_instance_count":1,'
                                 '"mongos_instance_placement_group":"no",'
                                 '"mongos_instance_type":"m3.2xlarge",'
                                 '"runner":"111.111.111.111",'
                                 '"status":"running",'
                                 '"topology":"test-cluster"}')

    @patch('common.terraform_config.generate_runner')
    def test_no_placement_group(self, mock_generate_runner):
        """Test cluster with placement group."""
        mock_generate_runner.return_value = '111.111.111.111'
        tf_config = terraform_config.TerraformConfiguration(
            topology="test-cluster",
            use_config=False,
            now=datetime.datetime(2016, 5, 25, 7, 11, 49, 131998))

        tf_config.define_instance(None, "mongos", 10, "m3.2xlarge")
        self._test_configuration(tf_config,
                                 '{"expire_on":"2016-5-27",'
                                 '"mongos_instance_count":10,'
                                 '"mongos_instance_placement_group":"no",'
                                 '"mongos_instance_type":"m3.2xlarge",'
                                 '"runner":"111.111.111.111",'
                                 '"status":"running",'
                                 '"topology":"test-cluster"}')

    def test_count_exception(self):
        """Test exception for invalid instance count."""
        tf_config = terraform_config.TerraformConfiguration("test-cluster", use_config=False)

        # test exception for wrong instance type
        with self.assertRaises(ValueError):
            tf_config.define_instance(None, "mongod", 10, "m4.2xlarge")

        with self.assertRaises(ValueError):
            tf_config.define_instance(None, "workload", 0, "c3.8xlarge")

    def test_generate_expire_on_tag(self):
        """Test expire-on tag generator."""
        tag = terraform_config.generate_expire_on_tag(
            now=datetime.datetime(2016, 5, 25, 7, 11, 49, 131998))
        self.assertEqual(tag, "2016-5-27")

        tag = terraform_config.generate_expire_on_tag(
            now=datetime.datetime(2016, 5, 31, 7, 11, 49, 131998))
        self.assertEqual(tag, "2016-6-2")

        tag = terraform_config.generate_expire_on_tag(
            now=datetime.datetime(2016, 12, 31, 7, 11, 49, 131998))
        self.assertEqual(tag, "2017-1-2")

    def test_placement_group_mapping(self):
        """Test proper mapping from instance type to whether support placement group."""

        self.assertEqual(True, terraform_config.support_placement_group("c3.8xlarge"))
        self.assertEqual(True, terraform_config.support_placement_group("m4.xlarege"))

        self.assertEqual(False, terraform_config.support_placement_group("m3.2xlarege"))

    @patch('common.terraform_config.generate_runner')
    def test_provisioning_file(self, mock_generate_runner):
        """Test cluster with provisioning file overwrite."""
        mock_generate_runner.return_value = '111.111.111.111'
        old_dir = os.getcwd()
        os.chdir(os.path.dirname(os.path.abspath(__file__)) + '/artifacts')

        tf_config = terraform_config.TerraformConfiguration(
            topology="test-cluster",
            now=datetime.datetime(2016, 5, 25, 7, 11, 49, 131998))

        self._test_configuration(tf_config,
                                 '{"availability_zone":"us-west-2b",'
                                 '"configsvr_instance_count":5,'
                                 '"configsvr_instance_placement_group":"no",'
                                 '"configsvr_instance_type":"m3.4xlarge",'
                                 '"expire_on":"2016-5-28",'
                                 '"key_file":"../../keys/aws.pem",'
                                 '"key_name":"serverteam-perf-ssh-key",'
                                 '"mongod_instance_count":15,'
                                 '"mongod_instance_placement_group":"yes",'
                                 '"mongod_instance_type":"c3.8xlarge",'
                                 '"mongos_instance_count":3,'
                                 '"mongos_instance_placement_group":"yes",'
                                 '"mongos_instance_type":"c3.8xlarge",'
                                 '"owner":"serverteam-perf@10gen.com",'
                                 '"region":"us-west-2",'
                                 '"runner":"111.111.111.111",'
                                 '"status":"running",'
                                 '"topology":"test-cluster",'
                                 '"workload_instance_count":1,'
                                 '"workload_instance_placement_group":"yes",'
                                 '"workload_instance_type":"c3.8xlarge"}')
        os.chdir(old_dir)
