"""test file for terraform_env"""

from __future__ import print_function
import unittest
import sys
import os
import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/common")
import terraform_config as t  # noqa; pylint: disable=E0401


class TestTerraformConfiguration(unittest.TestCase):
    """To test terraform configuration class"""

    def _test_configuration(self, tf_config, expected_output_string):
        json_string = tf_config.to_json(compact=True)
        self.assertEqual(json_string, expected_output_string)

    def test_default(self):
        """test default terraform configuration, that is to update expire-on only"""
        tf_config = t.TerraformConfiguration(now=datetime.datetime(2016, 5, 25, 7, 11, 49, 131998))
        json_string = tf_config.to_json(compact=True)

        self.assertEqual(json_string, '{"expire_on":"2016-5-26"}')

    def test_normal_cluster_definition(self):
        """test cluster with proper parameters"""
        tf_config = t.TerraformConfiguration(topology="test-cluster",
                                             now=datetime.datetime(2016, 5, 25, 7, 11, 49, 131998))

        tf_config.define_mongod_instance(10, "c3.8xlarge")
        self._test_configuration(tf_config,
                                 '{"expire_on":"2016-5-26",'
                                 '"mongod_instance_count":10,'
                                 '"mongod_instance_placement_group":"yes",'
                                 '"mongod_instance_type":"c3.8xlarge",'
                                 '"topology":"test-cluster"}')

    def test_large_cluster(self):
        """test cluster with mixed instances"""
        tf_config = t.TerraformConfiguration(topology="test-cluster",
                                             now=datetime.datetime(2016, 5, 25, 7, 11, 49, 131998))
        tf_config.define_mongos_instance(1, "m3.2xlarge")
        tf_config.define_mongod_instance(10, "c3.2xlarge")
        tf_config.define_configserver_instance(3, "m3.xlarge")
        self._test_configuration(tf_config,
                                 '{"configserver_instance_count":3,'
                                 '"configserver_instance_placement_group":"no",'
                                 '"configserver_instance_type":"m3.xlarge",'
                                 '"expire_on":"2016-5-26",'
                                 '"mongod_instance_count":10,'
                                 '"mongod_instance_placement_group":"yes",'
                                 '"mongod_instance_type":"c3.2xlarge",'
                                 '"mongos_instance_count":1,'
                                 '"mongos_instance_placement_group":"no",'
                                 '"mongos_instance_type":"m3.2xlarge",'
                                 '"topology":"test-cluster"}')

    def test_no_placement_group(self):
        """test clustenr with placement group"""
        tf_config = t.TerraformConfiguration(topology="test-cluster",
                                             now=datetime.datetime(2016, 5, 25, 7, 11, 49, 131998))
        tf_config.define_mongos_instance(10, "m3.2xlarge")
        self._test_configuration(tf_config,
                                 '{"expire_on":"2016-5-26",'
                                 '"mongos_instance_count":10,'
                                 '"mongos_instance_placement_group":"no",'
                                 '"mongos_instance_type":"m3.2xlarge",'
                                 '"topology":"test-cluster"}')

    def test_count_exception(self):
        """test exception for invalid instance count"""
        tf_config = t.TerraformConfiguration("test-cluster")
        with self.assertRaises(ValueError):
            tf_config.define_mongod_instance(0, "c3.8xlarge")

        # test exception for wrong instance type
        with self.assertRaises(ValueError):
            tf_config.define_mongod_instance(10, "m4.2xlarge")

        with self.assertRaises(ValueError):
            tf_config.define_workload_instance(0, "c3.8xlarge")

        with self.assertRaises(ValueError):
            tf_config.define_configserver_instance(0, "c3.8xlarge")

    def test_generate_expire_on_tag(self):
        """test expire-on tag generator"""
        tag = t.generate_expire_on_tag(now=datetime.datetime(2016, 5, 25, 7, 11, 49, 131998))
        self.assertEqual(tag, "2016-5-26")

        tag = t.generate_expire_on_tag(now=datetime.datetime(2016, 5, 31, 7, 11, 49, 131998))
        self.assertEqual(tag, "2016-6-1")

        tag = t.generate_expire_on_tag(now=datetime.datetime(2016, 12, 31, 7, 11, 49, 131998))
        self.assertEqual(tag, "2017-1-1")

    def test_placement_group_mapping(self):
        """test proper mapping from instance type to whether support placement group"""

        self.assertEqual(True, t.support_placement_group("c3.8xlarge"))
        self.assertEqual(True, t.support_placement_group("m4.xlarege"))

        self.assertEqual(False, t.support_placement_group("m3.2xlarege"))
