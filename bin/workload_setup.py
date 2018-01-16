#!/usr/bin/env python2.7
"""Setup hosts for running various kinds of workload types."""

import argparse
import logging
import sys

import common.host as host
from common.config import ConfigDict
from common.log import setup_logging

LOG = logging.getLogger(__name__)


class WorkloadSetupRunner(object):
    """Responsible for invoking workload_setup.yml commands before test_control."""

    def __init__(self, conf):
        """
        Constructor.

        :param conf: system config
        """
        self.conf = conf

    def test_types(self):
        """
        Indicates which test types we have in test_control.

        :return: test-types for which we need to run the associated
                 workload_setup blocks.
        :rtype   set(string)
        """
        return set([run['type'] for run in self.conf['test_control']['run']])

    def already_done(self):
        """
        Indicate if we've already completed workload setup.

        :return: boolean if we've already done our job before
                 as indicated by the config.
        """
        return 'out' in self.conf['workload_setup'] and \
               self.conf['workload_setup']['out']['done'] is True

    # Could make the case that this should actually call self.conf.save(),
    # but that would make it slightly harder to test with vanilla dicts,
    # plus this class is otherwise entirely in-memory.
    def mark_done(self):
        """
        Indicate in output configuration that we've completed workload setup.
        """
        if 'out' not in self.conf['workload_setup']:
            self.conf['workload_setup']['out'] = {}
        self.conf['workload_setup']['out']['done'] = True

    def setup_workloads(self):
        """
        Perform setup for all the required workload types.
        """
        for test_type in self.test_types():
            self.run_setup_for_test_type(test_type)
        self.mark_done()

    def run_setup_for_test_type(self, test_type):
        """
        Run setup for a particular test type.

        :param string test_type: workload_setup key listing commands to run
        :return: None
        """
        LOG.info("Starting workload_setup for test_type %s", test_type)
        steps = self.conf['workload_setup'][test_type]
        host.run_host_commands(steps, current_test_id=None, conf=self.conf)


def main(argv):
    """Parse args and call workload_setup.yml operations."""
    parser = argparse.ArgumentParser(description='Workload Setup')

    parser.add_argument('-d', '--debug', action='store_true', help='enable debug output')
    parser.add_argument('--log-file', help='path to log file')

    args = parser.parse_args(argv)
    setup_logging(args.debug, args.log_file)

    conf = ConfigDict('workload_setup')
    conf.load()

    setup = WorkloadSetupRunner(conf)
    setup.setup_workloads()

    conf.save()


if __name__ == '__main__':
    main(sys.argv[1:])
