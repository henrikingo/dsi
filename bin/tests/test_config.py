"""Tests for bin/common/config.py"""

# pylint: disable=fixme,line-too-long
import os
import sys
import unittest

import yaml

# TODO: Learn how to do this correctly without complaint from pylint
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/common")

from config import ConfigDict #pylint: disable=wrong-import-position,wrong-import-order

class ConfigDictTestCase(unittest.TestCase):
    """Unit tests for ConfigDict library."""

    def setUp(self):
        """Init a ConfigDict object and load the configuration files from docs/config-specs/"""
        self.old_dir = os.getcwd() # Save the old path to restore Note
        # that this chdir only works without breaking relative imports
        # because it's at the same directory depth
        os.chdir(os.path.dirname(os.path.abspath(__file__)) + '/../../docs/config-specs/')
        self.conf = ConfigDict('mongodb_setup')
        self.conf.load()
        self.assertEqual(self.conf.module, 'mongodb_setup')

    def tearDown(self):
        """Restore working directory"""
        os.chdir(self.old_dir)

    def test_traverse_entire_dict(self):
        """Traverse entire dict (also tests that the structure of docs/config-specs/ files are ok)"""
        # We actually could compare the result to a constant megadict here, but maintaining that
        # would quickly become tedious. In practice, there's huge value just knowing we can traverse
        # the entire structure without errors.
        str(self.conf)

    @unittest.skip("dict(instance_of_ConfigDict) does not work")
    def test_cast_as_dict(self):
        """It is possible to cast a ConfigDict to a dict"""
        # TODO: this doesn't actually work. Seems like a limitation of python when sub-classing
        # native type like dict: http://stackoverflow.com/questions/18317905/overloaded-iter-is-bypassed-when-deriving-from-dict
        complete_dict = dict(self.conf)
        sub_dict = dict(self.conf['workload_preparation']['on_workload_client'])
        self.assertEqual(complete_dict['workload_preparation']['on_workload_client']['download_files'][0],
                         'http://url1')
        self.assertEqual(sub_dict['download_files'][0], 'http://url1')

    def test_convert_to_dict(self):
        """It is possible to convert a ConfigDict to a dict with self.as_dict()"""
        complete_dict = self.conf.as_dict()
        sub_dict = self.conf['workload_preparation']['on_workload_client'].as_dict()
        self.assertEqual(complete_dict['workload_preparation']['on_workload_client']['download_files'][0],
                         'http://url1')
        self.assertEqual(sub_dict['download_files'][0], 'http://url1')

    def test_basic_checks(self):
        """Basic checks"""
        self.assertEqual(self.conf['workload_preparation']['on_workload_client']['download_files'][0], 'http://url1')
        self.assertEqual(self.conf['workload_preparation']['on_workload_client']['download_files'], ['http://url1'])
        self.assertEqualDicts(self.conf['infrastructure_provisioning']['out']['mongos'][2], {'public_ip': '53.1.1.102', 'private_ip': '10.2.1.102'})
        self.assertEqual(self.conf['infrastructure_provisioning']['out']['workload_client'][0]['public_ip'], "53.1.1.101")

    def test_overrides(self):
        """Test value from overrides.yml"""
        self.assertEqual(self.conf['infrastructure_provisioning']['tfvars']['configsvr_instance_type'], "t1.micro")
        self.assertEqualDicts(self.conf['infrastructure_provisioning']['tfvars'], {'mongos_instance_type': 'c3.8xlarge', 'availability_zone': 'us-west-2a', 'workload_instance_count': 1, 'region': 'us-west-2', 'mongod_instance_count': 9, 'configsvr_instance_count': 3, 'mongos_instance_count': 3, 'ssh_key_file': 'aws_ssh_key.pem', 'ssh_user': 'ec2-user', 'mongod_instance_type': 'c3.8xlarge', 'ssh_key_name': 'server-perf-team-ssh-key', 'workload_instance_type': 'c3.8xlarge', 'tags': {'Project': 'sys-perf', 'owner': 'perf@10gen.com', 'Variant': 'Linux 3-shard cluster', 'Name': 'server-perf-myvariant', 'expire-on-delta': 1}, 'configsvr_instance_type': 't1.micro'})

    def test_defaults(self):
        """Test value from defaults.yml"""
        self.assertEqual(self.conf['mongodb_setup']['mongod_config_file']['net']['port'], 27017)
        self.assertEqual(self.conf['mongodb_setup']['mongod_config_file']['processManagement']['fork'], True)

    def test_copy(self):
        """Copy value into new python variable"""
        out = self.conf['infrastructure_provisioning']['out']
        self.conf.raw['infrastructure_provisioning']['out']['workload_client'][0]['private_ip'] = "foo"
        out.raw['workload_client'][0]['public_ip'] = "bar"
        self.assertTrue(isinstance(out, ConfigDict))
        self.assertEqualLists(self.conf.raw['infrastructure_provisioning']['out']['workload_client'],
                              [{'public_ip': 'bar', 'private_ip': 'foo'}])
        self.assertEqualLists(self.conf.root['infrastructure_provisioning']['out']['workload_client'],
                              [{'public_ip': 'bar', 'private_ip': 'foo'}])
        self.assertEqualLists(out.raw['workload_client'],
                              [{'public_ip': 'bar', 'private_ip': 'foo'}])
        self.assertEqualLists(out.root['infrastructure_provisioning']['out']['workload_client'],
                              [{'public_ip': 'bar', 'private_ip': 'foo'}])
        self.assertEqualDicts(out.overrides, {})
        self.assertEqual(out['workload_client'][0]['public_ip'], 'bar')

    def test_variable_references(self):
        """Test ${variable.references}"""
        self.assertEqual(self.conf['mongodb_setup']['topology'][0]['mongos'][0]['private_ip'], "10.2.1.100")
        self.assertEqual(self.conf['mongodb_setup']['meta']['hosts'], "10.2.1.100:27017,10.2.1.101:27017,10.2.1.102:27017")

    def test_per_node_mongod_config(self):
        """Test magic per_node_mongod_config() (merging the common mongod_config_file with per node config_file)"""
        mycluster = self.conf['mongodb_setup']['topology'][0]
        mongod = mycluster['shard'][2]['mongod'][0]
        self.assertEqualDicts(mycluster['shard'][0]['mongod'][0]['config_file'], {'replication': {'oplogSizeMB': 153600, 'replSetName': 'override-rs'}, 'systemLog': {'path': 'data/logs/mongod.log', 'destination': 'file'}, 'setParameter': {'enableTestCommands': True, 'foo': True}, 'net': {'port': 27017}, 'processManagement': {'fork': True}, 'storage': {'engine': 'wiredTiger', 'dbPath': 'data/dbs'}})
        self.assertEqualDicts(mycluster['shard'][2]['mongod'][0]['config_file'], {'replication': {'oplogSizeMB': 153600, 'replSetName': 'override-rs'}, 'systemLog': {'path': 'data/logs/mongod.log', 'destination': 'file'}, 'setParameter': {'enableTestCommands': True, 'foo': True}, 'net': {'port': 27017}, 'processManagement': {'fork': True}, 'storage': {'engine': 'inMemory', 'dbPath': 'data/dbs'}})
        self.assertEqualDicts(mycluster['shard'][2]['mongod'][0]['config_file'].overrides, {})
        self.assertEqual(mycluster['shard'][2]['mongod'][0]['config_file']['storage']['engine'], "inMemory")
        self.assertEqual(mycluster['shard'][2]['mongod'][0]['config_file']['net']['port'], 27017)
        self.assertEqual(mycluster['shard'][2]['mongod'][0]['config_file']['processManagement']['fork'], True)
        self.assertEqual(mongod.raw, {'public_ip': '${infrastructure_provisioning.out.mongod.6.public_ip}', 'mongodb_binary_archive': '<another url>', 'config_file': {'storage': {'engine': 'inMemory'}}, 'private_ip': '${infrastructure_provisioning.out.mongod.6.private_ip}'})
        # Standalone node
        self.assertEqualDicts(self.conf['mongodb_setup']['topology'][2]['config_file'], {'replication': {'oplogSizeMB': 153600, 'replSetName': 'override-rs'}, 'systemLog': {'path': 'data/logs/mongod.log', 'destination': 'file'}, 'setParameter': {'enableTestCommands': True, 'foo': True}, 'net': {'port': 27017}, 'processManagement': {'fork': True}, 'storage': {'engine': 'wiredTiger', 'dbPath': 'data/dbs'}})
        # self.keys() should return a 'config_file' key
        self.assertTrue('config_file' in mycluster['shard'][0]['mongod'][0].keys())
        self.assertTrue('config_file' in mycluster['shard'][2]['mongod'][0].keys())
        self.assertTrue('config_file' in self.conf['mongodb_setup']['topology'][2].keys())
        self.assertFalse('config_file' in self.conf['mongodb_setup']['topology'][0].keys())

    def test_replset_rs_conf(self):
        """Test magic rs_conf for a replset"""
        mycluster = self.conf['mongodb_setup']['topology'][0]
        rs_conf = mycluster['shard'][2]['rs_conf']
        self.assertEqual(rs_conf['protocolVersion'], 1)
        myreplset = self.conf['mongodb_setup']['topology'][1]
        rs_conf = myreplset['rs_conf']
        self.assertEqual(rs_conf['settings']['chainingAllowed'], False)
        self.assertEqual(rs_conf['protocolVersion'], 1)

        # conf.keys() should return a 'config_file' key for replsets, not otherwise
        self.assertTrue('rs_conf' in mycluster['shard'][0].keys())
        self.assertTrue('rs_conf' in mycluster['shard'][2].keys())
        self.assertTrue('rs_conf' in myreplset.keys())
        self.assertFalse('rs_conf' in mycluster.keys())
        self.assertFalse('rs_conf' in self.conf['mongodb_setup']['topology'][2].keys())
        self.assertFalse('rs_conf' in self.conf['infrastructure_provisioning'].keys())

    def test_set_some_values(self):
        """Set some values and write out file"""
        self.conf['mongodb_setup']['out'] = {'foo' : 'bar'}
        # Read the value multiple times, because once upon a time that didn't work (believe it or not)
        self.assertEqualDicts(self.conf['mongodb_setup']['out'], {'foo': 'bar'})
        self.assertEqualDicts(self.conf['mongodb_setup']['out'], {'foo': 'bar'})
        self.assertEqualDicts(self.conf['mongodb_setup']['out'], {'foo': 'bar'})
        self.conf['mongodb_setup']['out']['zoo'] = 'zar'
        self.assertEqualDicts(self.conf['mongodb_setup']['out'], {'foo': 'bar', 'zoo': 'zar'})
        with self.assertRaises(KeyError):
            self.conf['foo'] = 'bar'
        # Write the out file only if it doesn't already exist, and delete it when done
        file_name = '../../docs/config-specs/mongodb_setup.out.yml'
        if os.path.exists(file_name):
            self.fail("Cannot test writing docs/config-specs/mongodb_setup.out.yml file, file already exists.")
        else:
            self.conf.save()
            file_handle = open(file_name)
            saved_out_file = yaml.safe_load(file_handle)
            file_handle.close()
            self.assertEqualDicts({'out' : self.conf['mongodb_setup']['out']}, saved_out_file)
            os.remove(file_name)

    def test_iterators(self):
        """Test that iterators .keys() and .values() work"""
        mycluster = self.conf['mongodb_setup']['topology'][0]
        self.assertEqualLists(self.conf.keys(), ['workload_preparation', 'test_control', 'system_setup', 'runtime_secret', 'bootstrap', 'mongodb_setup', 'analysis', 'infrastructure_provisioning', 'runtime'])
        self.assertEqualLists(self.conf['infrastructure_provisioning']['tfvars'].values(), ['c3.8xlarge', 'us-west-2a', 1, 'us-west-2', 9, 3, 3, 'aws_ssh_key.pem', 'ec2-user', 'c3.8xlarge', 'server-perf-team-ssh-key', 'c3.8xlarge', {'Project': 'sys-perf', 'owner': 'perf@10gen.com', 'Variant': 'Linux 3-shard cluster', 'Name': 'server-perf-myvariant', 'expire-on-delta': 1}, 't1.micro'])
        self.assertEqualLists(mycluster['shard'][2]['mongod'][0].values(), ['53.1.1.7', '<another url>', {'replication': {'oplogSizeMB': 153600, 'replSetName': 'override-rs'}, 'systemLog': {'path': 'data/logs/mongod.log', 'destination': 'file'}, 'setParameter': {'enableTestCommands': True, 'foo': True}, 'net': {'port': 27017}, 'processManagement': {'fork': True}, 'storage': {'engine': 'inMemory', 'dbPath': 'data/dbs'}}, '10.2.1.7'])

    # Helpers
    # pylint: disable=invalid-name
    # ...to follow conventions of unnittest.TestCase API
    def assertEqualDicts(self, dict1, dict2):
        """Compare 2 dicts element by element for equal values."""
        dict1keys = dict1.keys()
        dict2keys = dict2.keys()
        self.assertEqual(len(dict1keys), len(dict2keys))
        for dict1key in dict1keys:
            # Pop the corresponding key from dict2, note that they won't be in the same order.
            dict2key = dict2keys.pop(dict2keys.index(dict1key))
            self.assertEqual(dict1key, dict2key, 'assertEqualDicts failed: mismatch in keys: ' + str(dict1key) + '!=' + str(dict2key))
            if isinstance(dict1[dict1key], dict):
                self.assertEqualDicts(dict1[dict1key], dict2[dict2key])
            elif isinstance(dict1[dict1key], list):
                self.assertEqualLists(dict1[dict1key], dict2[dict2key])
            else:
                self.assertEqual(dict1[dict1key], dict2[dict2key], 'assertEqualDicts failed: mismatch in values.')
        self.assertEqual(len(dict2keys), 0)

    def assertEqualLists(self, list1, list2):
        """Compare 2 lists element by element for equal values."""
        self.assertEqual(len(list1), len(list2))
        for list1value in list1:
            list2value = list2.pop(0)
            if isinstance(list1value, dict):
                self.assertEqualDicts(list1value, list2value)
            elif isinstance(list1value, list):
                self.assertEqualLists(list1value, list2value)
            else:
                self.assertEqual(list1value, list2value, 'assertEqualLists failed: mismatch in values.')
        self.assertEqual(len(list2), 0)


if __name__ == '__main__':
    unittest.main()
