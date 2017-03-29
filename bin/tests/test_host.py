"""Tests for bin/common/host.py"""

import os
import sys
import unittest

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/common")

from config import ConfigDict
import host

class HostTestCase(unittest.TestCase):
    '''Unit Test for Host library'''

    def setUp(self):
        """Init a ConfigDict object and load the configuration files from docs/config-specs/"""
        self.old_dir = os.getcwd() # Save the old path to restore Note
        # that this chdir only works without breaking relative imports
        # because it's at the same directory depth
        os.chdir(os.path.dirname(os.path.abspath(__file__)) + '/../../docs/config-specs/')
        self.config = ConfigDict('mongodb_setup')
        self.config.load()

    def tearDown(self):
        """Restore working directory"""
        os.chdir(self.old_dir)

    def test_extract_hosts(self):
        ''' Test extract hosts using config info'''
        mongods = ['53.1.1.1',
                   '53.1.1.2',
                   '53.1.1.3',
                   '53.1.1.4',
                   '53.1.1.5',
                   '53.1.1.6',
                   '53.1.1.7',
                   '53.1.1.8',
                   '53.1.1.9']
        configsvrs = ['53.1.1.51',
                      '53.1.1.52',
                      '53.1.1.53',]
        mongos = ['53.1.1.100',
                  '53.1.1.101',
                  '53.1.1.102']
        workload_clients = ['53.1.1.101']
        self.assertEqual(host.extract_hosts('localhost', self.config), ['localhost'])
        self.assertEqual(host.extract_hosts('workload_client', self.config), workload_clients)
        self.assertEqual(host.extract_hosts('mongod', self.config), mongods)
        self.assertEqual(host.extract_hosts('mongos', self.config), mongos)
        self.assertEqual(host.extract_hosts('configsvr', self.config), configsvrs)
        self.assertEqual(host.extract_hosts('all_servers', self.config),
                         mongods + mongos + configsvrs)
        self.assertEqual(host.extract_hosts('all_hosts', self.config),
                         mongods + mongos + configsvrs + workload_clients)

