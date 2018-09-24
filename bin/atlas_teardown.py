#!/usr/bin/env python2.7
"""
Destroy an Atlas cluster.
"""
import argparse
import logging
import sys

import atlas_setup
import common.config as config
import common.log as log

LOG = logging.getLogger(__name__)


def parse_command_line():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Start a MongoDB cluster in Atlas')
    parser.add_argument('-d', '--debug', action='store_true', help='enable debug output')
    parser.add_argument('--log-file', help='path to log file')

    return parser.parse_args()


def main():
    """ Handle the main functionality (parse args /setup logging ) then call teardown."""
    args = parse_command_line()
    log.setup_logging(args.debug, args.log_file)
    LOG.info("atlas_teardown.py start")

    conf = config.ConfigDict('mongodb_setup')
    conf.load()

    # start a mongodb configuration using config
    atlas = atlas_setup.AtlasSetup(conf)
    if atlas.destroy():
        LOG.info("atlas_teardown.py end -- AtlasSetup.destroy() success")
        return 0

    LOG.info("atlas_teardown.py end -- AtlasSetup.destroy() failed")
    return 1


if __name__ == '__main__':
    sys.exit(main())
