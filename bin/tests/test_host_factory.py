"""Tests for bin/common/host.py"""

import unittest

from mock import patch

import common.models.host_info as host_info
import common.host_factory


class HostFactoryTestCase(unittest.TestCase):
    """ Unit Test for Host Factory library """

    @patch("paramiko.SSHClient")
    def test_make_host(self, mock_ssh):
        """ Test make host """

        my_host_info = host_info.HostInfo(
            public_ip="53.1.1.1", offset=0, ssh_user="ssh_user", ssh_key_file="ssh_key_file"
        )

        my_host_info.category = "mongod"
        mongod = common.host_factory.make_host(my_host_info)
        self.assertEqual(mongod.alias, "mongod.0", "alias not set as expected")

        my_host_info.category = "mongos"
        my_host_info.offset = 1
        mongos = common.host_factory.make_host(my_host_info)
        self.assertEqual(mongos.alias, "mongos.1", "alias not set as expected")

        my_host_info.category = "localhost"
        for my_ip in ["localhost", "127.0.0.1", "0.0.0.0"]:
            my_host_info.public_ip = my_ip
            localhost = common.host_factory.make_host(my_host_info)
            self.assertEqual(localhost.alias, "localhost.1", "alias not set as expected")


if __name__ == "__main__":
    unittest.main()
