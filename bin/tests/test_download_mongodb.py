"""Tests for bin/common/download_mongodb.py"""

import os
import sys
import unittest

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/common")

from download_mongodb import DownloadMongodb #pylint: disable=wrong-import-position

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
                       'mongodb_setup' :
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
                                 'mongodb_setup' :  {}
                                }
        self.cli_mongodb_binary_archive = 'http://bar.tgz'
        self.downloader = None


    def test_basic_use(self):
        """Init DownloadMongodb with ConfigDict structure."""
        mongodb = self.config['mongodb_setup']
        infrastructure = self.config['infrastructure_provisioning']
        # Must use run_locally=True for testing. RemoteHost opens connections already in __init__.
        self.downloader = DownloadMongodb(self.config, None, True)
        self.assertTrue(self.downloader)
        self.assertEqual(self.downloader.mongodb_binary_archive, mongodb['mongodb_binary_archive'])
        self.assertEqual(self.downloader.ssh_key_file, infrastructure['tfvars']['ssh_key_file'])
        self.assertEqual(self.downloader.ssh_user, infrastructure['tfvars']['ssh_user'])
        # TODO: Can't really unit test anything that uses RemoteHost for now, so can't assert the
        # parsing of public_ip's. Need to mock RemoteHost or something

    def test_cli_binary_with_config(self):
        """Pass mongodb_binary_archive as command line option. Note: The one in config wins."""
        mongodb = self.config['mongodb_setup']
        # Must use run_locally=True for testing. RemoteHost opens connections already in __init__.
        self.downloader = DownloadMongodb(self.config, self.cli_mongodb_binary_archive, True)
        self.assertEqual(self.downloader.mongodb_binary_archive, mongodb['mongodb_binary_archive'])

    def test_cli_binary_only(self):
        """Pass mongodb_binary_archive as command line option without any specified in config."""
        # Must use run_locally=True for testing. RemoteHost opens connections already in __init__.
        self.downloader = DownloadMongodb(self.config_no_binary,
                                          self.cli_mongodb_binary_archive, True)
        self.assertEqual(self.downloader.mongodb_binary_archive, self.cli_mongodb_binary_archive)

if __name__ == '__main__':
    unittest.main()
