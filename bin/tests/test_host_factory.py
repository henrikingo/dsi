"""Tests for bin/common/host.py"""

import unittest

from mock import patch

import common.host_factory


class HostFactoryTestCase(unittest.TestCase):
    """ Unit Test for Host Factory library """

    @patch('paramiko.SSHClient')
    def test_make_host(self, mock_ssh):
        """ Test make host """

        host_info = common.host_utils.HostInfo('53.1.1.1', "mongod", 0)
        mongod = common.host_factory.make_host(host_info, "ssh_user", "ssh_key_file")
        self.assertEqual(mongod.alias, 'mongod.0', "alias not set as expected")

        host_info = common.host_utils.HostInfo('53.0.0.1', "mongos", 1)
        mongos = common.host_factory.make_host(host_info, "ssh_user", "ssh_key_file")
        self.assertEqual(mongos.alias, 'mongos.1', "alias not set as expected")

        for ip_or_name in ['localhost', '127.0.0.1', '0.0.0.0']:
            host_info = common.host_utils.HostInfo(ip_or_name, "localhost", 0)
            localhost = common.host_factory.make_host(host_info, "ssh_user", "ssh_key_file")
            self.assertEqual(localhost.alias, 'localhost.0', "alias not set as expected")


if __name__ == '__main__':
    unittest.main()
