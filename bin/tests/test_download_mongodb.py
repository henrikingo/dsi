"""Tests for bin/common/download_mongodb.py"""
# pylint: disable=protected-access
import os
from collections import namedtuple

import sys
import unittest
import string

from mock import patch

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/common")

from download_mongodb import DownloadMongodb, temp_file  # pylint: disable=wrong-import-position

class DownloadMongodbTestCase(unittest.TestCase):
    """Unit tests for DownloadMongodb library."""

    def setUp(self):
        """Init a DownloadMongodb object"""
        self.config = {'infrastructure_provisioning' :
                       {'tfvars' :
                        {'ssh_user' : 'ec2-user', 'ssh_key_file' : '../../aws.pem'},
                        'out':
                        {'mongod': [
                            {'public_ip' : '10.2.3.4', 'private_ip' : '10.0.0.1'},
                            {'public_ip' : '10.2.3.5', 'private_ip' : '10.0.0.2'},
                            {'public_ip' : '10.2.3.6', 'private_ip' : '10.0.0.3'},
                            {'public_ip' : '10.2.3.7', 'private_ip' : '10.0.0.4'},
                            {'public_ip' : '10.2.3.8', 'private_ip' : '10.0.0.5'}],
                         'mongos' : [
                             {'public_ip' : '10.2.3.9', 'private_ip' : '10.0.0.6'},
                             {'public_ip' : '10.2.3.10', 'private_ip' : '10.0.0.7'},
                             {'public_ip' : '10.2.3.11', 'private_ip' : '10.0.0.8'}],
                         'configsvr' : [
                             {'public_ip' : '10.2.3.12', 'private_ip' : '10.0.0.9'},
                             {'public_ip' : '10.2.3.13', 'private_ip' : '10.0.0.10'},
                             {'public_ip' : '10.2.3.14', 'private_ip' : '10.0.0.11'}],
                         'workload_client' : [
                             {'public_ip' : '10.2.3.15', 'private_ip' : '10.0.0.12'}]
                        }
                       },
                       'runtime' :
                           {'mongodb_binary_archive' : 'http://foo.tgz'}
                      }
        self.config_no_binary = {'infrastructure_provisioning' :
                                 {'tfvars' :
                                  {'ssh_user' : 'ec2-user', 'ssh_key_file' : '../../aws.pem'},
                                  'out' :
                                  {'mongod' : [
                                      {'public_ip' : '10.2.3.4', 'private_ip' : '10.0.0.1'}],
                                   'workload_client' : [
                                       {'public_ip' : '10.2.3.15', 'private_ip' : '10.0.0.12'}]
                                  }
                                 },
                                 'runtime' :  {},
                                 'mongodb_setup' : {'mongo_dir' : '/tmp'}
                                }
        self.cli_mongodb_binary_archive = 'http://bar.tgz'
        self.downloader = None


    def test_basic_use(self):
        """Init DownloadMongodb with ConfigDict structure."""
        runtime = self.config['runtime']
        infrastructure = self.config['infrastructure_provisioning']
        # Must use run_locally=True for testing. RemoteHost opens connections already in __init__.
        self.downloader = DownloadMongodb(self.config, None, True)
        self.assertTrue(self.downloader)
        self.assertEqual(self.downloader.mongodb_binary_archive, runtime['mongodb_binary_archive'])
        self.assertEqual(self.downloader.ssh_key_file, infrastructure['tfvars']['ssh_key_file'])
        self.assertEqual(self.downloader.ssh_user, infrastructure['tfvars']['ssh_user'])
        # TODO: Can't really unit test anything that uses RemoteHost for now, so can't assert the
        # parsing of public_ip's. Need to mock RemoteHost or something

    def test_cli_binary_with_config(self):
        """Pass mongodb_binary_archive as command line option. Note: The one in config wins."""
        runtime = self.config['runtime']
        # Must use run_locally=True for testing. RemoteHost opens connections already in __init__.
        self.downloader = DownloadMongodb(self.config, self.cli_mongodb_binary_archive, True)
        self.assertEqual(self.downloader.mongodb_binary_archive, runtime['mongodb_binary_archive'])

    def test_cli_binary_only(self):
        """Pass mongodb_binary_archive as command line option without any specified in config."""
        # Must use run_locally=True for testing. RemoteHost opens connections already in __init__.
        self.downloader = DownloadMongodb(self.config_no_binary,
                                          self.cli_mongodb_binary_archive, True)
        self.assertEqual(self.downloader.mongodb_binary_archive, self.cli_mongodb_binary_archive)

    def test_temp_file(self):
        """Pass mongodb_binary_archive as command line option without any specified in config."""
        # Must use run_locally=True for testing. RemoteHost opens connections already in __init__.

        def _test_temp_file(test, filename, value, uuid_len=36):
            test.assertTrue(filename.endswith(value))
            test.assertTrue(len(filename) == len(value) + uuid_len)

        _test_temp_file(self, temp_file(), "mongodb.tgz")
        _test_temp_file(self, temp_file(path=self.cli_mongodb_binary_archive), "bar.tgz")
        _test_temp_file(self, temp_file(path=self.cli_mongodb_binary_archive + "?test=ing"),
                        "bar.tgztesting")
        path = self.cli_mongodb_binary_archive + "?test=ing&second=param"
        _test_temp_file(self, temp_file(path=path), "bar.tgztestingsecondparam")

        # the '/' chars wouldn't have survived the basename, which is why they are removed
        path = ''.join(sorted(string.printable.split())).replace("/", "")
        _test_temp_file(self, temp_file(path=path),
                        (string.digits + string.ascii_letters + "-._").replace("/", ""))

        # test sanitize allows everything
        path = self.cli_mongodb_binary_archive + "?test=ing"
        _test_temp_file(self, temp_file(path=path, sanitize=lambda x: x),
                        "bar.tgz?test=ing")

    @patch('download_mongodb.temp_file')
    def test_remove_temp_file(self, mock_temp_file):
        """test that mongo_dir and tmp_file removal."""
        # Must use run_locally=True for testing. RemoteHost opens connections already in __init__.

        tmp_file = '/tmp/bar.tgz'
        mock_temp_file.return_value = os.path.basename(tmp_file)
        self.downloader = DownloadMongodb(self.config_no_binary,
                                          self.cli_mongodb_binary_archive, True)
        commands = self.downloader._remote_commands(namedtuple('Host', 'host')._make(['host']))
        rm_mongo_dir = ['rm', '-rf', '/tmp']
        rm_tmp_file = ['rm', '-f', tmp_file]
        self.assertTrue(rm_mongo_dir in commands)
        self.assertTrue(rm_tmp_file in commands)
        self.assertTrue(commands.index(rm_mongo_dir) < commands.index(rm_tmp_file))

if __name__ == '__main__':
    unittest.main()
