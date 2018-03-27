"""Tests for bin/common/host_utils.py"""

import unittest
from datetime import datetime
import os
import time
import shutil
import socket
from StringIO import StringIO

from mock import patch, MagicMock, call

import common.host_utils
from common.config import ConfigDict

# Useful absolute directory paths.
FIXTURE_DIR_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "unittest-files")


def fixture_file_path(file_path):
    """Return the absolute path of a file at `file_path` inside the fixture files directory."""

    return os.path.join(FIXTURE_DIR_PATH, file_path)


class HostUtilsTestCase(unittest.TestCase):
    """ Unit Tests for Host Utils library """

    def _delete_fixtures(self):
        """ delete fixture path and set filename attribute """
        local_host_path = fixture_file_path('fixtures')
        self.filename = os.path.join(local_host_path, 'file')
        shutil.rmtree(os.path.dirname(self.filename), ignore_errors=True)

    def setUp(self):
        """ Init a ConfigDict object and load the configuration files from docs/config-specs/ """
        self.old_dir = os.getcwd()  # Save the old path to restore
        # Note that this chdir only works without breaking relative imports
        # because it's at the same directory depth
        os.chdir(os.path.dirname(os.path.abspath(__file__)) + '/../../docs/config-specs/')
        self.config = ConfigDict('mongodb_setup')
        self.config.load()
        self.parent_dir = os.path.join(os.path.expanduser('~'), 'checkout_repos_test')

        self._delete_fixtures()

    def tearDown(self):
        """ Restore working directory """
        os.chdir(self.old_dir)

        self._delete_fixtures()

    def test_never_timeout(self):
        """ test never_timeout"""
        self.assertFalse(common.host_utils.never_timeout())
        self.assertFalse(common.host_utils.never_timeout())

    def test_check_timed_out(self):
        """ test check_timed_out"""
        start = datetime.now()
        self.assertFalse(common.host_utils.check_timed_out(start, 50))
        time.sleep(51 / 1000.0)
        self.assertTrue(common.host_utils.check_timed_out(start, 50))

    def test_create_timer(self):
        """ test create_timer """
        start = datetime.now()
        self.assertEquals(
            common.host_utils.create_timer(start, None), common.host_utils.never_timeout)
        with patch('common.host_utils.partial') as mock_partial:
            self.assertTrue(common.host_utils.create_timer(start, 50))
            mock_partial.assert_called_once_with(common.host_utils.check_timed_out, start, 50)

    def test_extract_hosts(self):
        """ Test extract hosts using config info """
        mongods = [
            common.host_utils.HostInfo('53.1.1.{}'.format(i + 1), "mongod", i) for i in range(0, 9)
        ]
        configsvrs = [
            common.host_utils.HostInfo('53.1.1.{}'.format(i + 51), "configsvr", i)
            for i in range(0, 3)
        ]
        mongos = [
            common.host_utils.HostInfo('53.1.1.{}'.format(i + 100), "mongos", i)
            for i in range(0, 3)
        ]
        workload_clients = [common.host_utils.HostInfo('53.1.1.101', "workload_client", 0)]
        localhost = [common.host_utils.HostInfo('localhost', 'localhost', 0)]

        self.assertEqual(common.host_utils.extract_hosts('localhost', self.config), localhost)
        self.assertEqual(
            common.host_utils.extract_hosts('workload_client', self.config), workload_clients)
        self.assertEqual(common.host_utils.extract_hosts('mongod', self.config), mongods)
        self.assertEqual(common.host_utils.extract_hosts('mongos', self.config), mongos)
        self.assertEqual(common.host_utils.extract_hosts('configsvr', self.config), configsvrs)
        self.assertEqual(
            common.host_utils.extract_hosts('all_servers', self.config),
            mongods + mongos + configsvrs)
        self.assertEqual(
            common.host_utils.extract_hosts('all_hosts', self.config),
            mongods + mongos + configsvrs + workload_clients)

    def test_stream_lines(self):
        """ Test stream_lines """

        source = StringIO('source')
        destination = MagicMock(name="destination")
        source.next = MagicMock(name="in")
        source.next.side_effect = socket.timeout('args')
        any_lines = common.host_utils.stream_lines(source, destination)
        self.assertEquals(False, any_lines)
        destination.write.assert_not_called()

        destination = MagicMock(name="destination")
        source.next = MagicMock(name="in")
        source.next.side_effect = ['first', 'second', socket.timeout('args'), 'third']
        any_lines = common.host_utils.stream_lines(source, destination)
        self.assertEquals(True, any_lines)

        calls = [
            call('first'),
            call('second'),
        ]

        destination.write.assert_has_calls(calls)


if __name__ == '__main__':
    unittest.main()
