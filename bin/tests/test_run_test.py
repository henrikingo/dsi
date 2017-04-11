"""Tests for bin/common/host.py"""

import os
import sys
import unittest

from mock import patch

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/common")

from config import ConfigDict
import host
from run_test import copy_timeseries


class RunTestTestCase(unittest.TestCase):
    """ Unit Test for Host library """

    def setUp(self):
        """ Init a ConfigDict object and load the configuration files from docs/config-specs/ """
        self.old_dir = os.getcwd() # Save the old path to restore Note
        # that this chdir only works without breaking relative imports
        # because it's at the same directory depth
        os.chdir(os.path.dirname(os.path.abspath(__file__)) + '/../../docs/config-specs/')
        self.config = ConfigDict('mongodb_setup')
        self.config.load()

    def tearDown(self):
        """ Restore working directory """
        os.chdir(self.old_dir)

    @patch('os.walk')
    @patch('run_test.extract_hosts')
    @patch('shutil.copyfile')
    def test__retrieve_file(self, mock_copyfile, mock_hosts, mock_walk):
        """ Test run RunTest.copy_timeseries. """

        mock_walk.return_value = []
        mock_hosts.return_value = []
        copy_timeseries(self.config)
        self.assertFalse(mock_copyfile.called)

        mock_walk.return_value = []
        mock_hosts.return_value = []
        copy_timeseries(self.config)
        self.assertFalse(mock_copyfile.called)

        mock_walk.reset_mock()
        mock_hosts.reset_mock()
        mock_copyfile.reset_mock()

        mock_walk.return_value = [
            ('/dirpath', ('dirnames',), ()),
            ]
        mock_hosts.return_value = [host.HostInfo('10.0.0.0', 'mongod', 0)]

        copy_timeseries(self.config)
        self.assertFalse(mock_copyfile.called)

        mock_walk.reset_mock()
        mock_hosts.reset_mock()
        mock_copyfile.reset_mock()
        mock_walk.return_value = [
            ('/dirpath', ('dirnames',), ('baz',)),
            ]
        mock_hosts.return_value = [host.HostInfo('10.0.0.0', 'mongod', 0)]

        copy_timeseries(self.config)
        self.assertFalse(mock_copyfile.called)

        mock_walk.reset_mock()
        mock_hosts.reset_mock()
        mock_copyfile.reset_mock()
        mock_walk.return_value = [
            ('/dirpath', ('dirnames',), ('10.0.0.0--notmatching',)),
            ('/foo/bar', (), ('spam', 'eggs')),
            ]
        mock_hosts.return_value = [host.HostInfo('10.0.0.0', 'mongod', 0)]

        copy_timeseries(self.config)
        self.assertFalse(mock_copyfile.called)

        mock_walk.reset_mock()
        mock_hosts.reset_mock()
        mock_copyfile.reset_mock()
        mock_walk.return_value = [
            ('/dirpath', ('dirnames',), ('matching--10.0.0.0',)),
            ]
        mock_hosts.return_value = [host.HostInfo('10.0.0.0', 'mongod', 0)]

        copy_timeseries(self.config)
        self.assertTrue(mock_copyfile.called_with('/dirpath/matching--10.0.0.0',
                                                  'reports/mongod.0/matching-dirpath'))

        mock_walk.reset_mock()
        mock_hosts.reset_mock()
        mock_copyfile.reset_mock()
        mock_walk.return_value = [
            ('/dirpath0', ('dirnames0',), ('file0--10.0.0.0',)),
            ('/dirpath1', ('dirnames1',), ('file1--10.0.0.1',)),
            ('/dirpath2', ('dirnames2',), ('file2--10.0.0.2',)),
            ]
        mock_hosts.return_value = [host.HostInfo('10.0.0.0', 'mongod', 0),
                                   host.HostInfo('10.0.0.1', 'mongod', 1)]

        copy_timeseries(self.config)
        self.assertTrue(mock_copyfile.called)
        self.assertTrue(mock_copyfile.called_with('/dirpath0/file0--10.0.0.0',
                                                  'reports/mongod.0/matching-dirpath0'))
        self.assertTrue(mock_copyfile.called_with('/dirpath1/file1--10.0.0.1',
                                                  'reports/mongod.1/matching-dirpath1'))


if __name__ == '__main__':
    unittest.main()
