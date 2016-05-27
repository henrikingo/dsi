
'''test file for terraform_env'''

from __future__ import print_function
import unittest
import sys
import os
import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/common")
import terraform_config as t  #pylint: disable=E0401

class TestTerraformConfiguration(unittest.TestCase):
    '''To test terraform configuration'''

    def test_default(self):
        '''test default terraform configuration, that is to update expire-on only'''
        tf_config = t.TerraformConfiguration(now=datetime.datetime(2016, 5, 25, 7, 11, 49, 131998))
        json_string = tf_config.to_json(compact=True)

        self.assertEqual(json_string, \
            '{"expire_on":"2016-5-26"}')

    def test_mongod_instance(self):
        '''test mongod instance parameters'''
        tf_config = t.TerraformConfiguration(topology="test-cluster",\
                    now=datetime.datetime(2016, 5, 25, 7, 11, 49, 131998))
        tf_config.define_mongod_instance(10, "c3.8xlarge")
        json_string = tf_config.to_json(compact=True)

        self.assertEqual(json_string, \
            '{"expire_on":"2016-5-26","mongod_instance_count":10,"mongod_instance_type":'\
            '"c3.8xlarge","topology":"test-cluster"}')

    def test_count_exception(self):
        '''test exception for invalid instance count'''
        tf_config = t.TerraformConfiguration("test-cluster")
        with self.assertRaises(ValueError):
            tf_config.define_mongod_instance(0, "c3.8xlarge")

        with self.assertRaises(ValueError):
            tf_config.define_workload_instance(0, "c3.8xlarge")

    def test_generate_expire_on_tag(self):
        '''test expire-on tag generator'''
        tag = t.generate_expire_on_tag(now=datetime.datetime(2016, 5, 25, 7, 11, 49, 131998))
        self.assertEqual(tag, "2016-5-26")

        tag = t.generate_expire_on_tag(now=datetime.datetime(2016, 5, 31, 7, 11, 49, 131998))
        self.assertEqual(tag, "2016-6-1")

        tag = t.generate_expire_on_tag(now=datetime.datetime(2016, 12, 31, 7, 11, 49, 131998))
        self.assertEqual(tag, "2017-1-1")
