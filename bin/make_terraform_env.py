#!/usr/bin/env python2.7
# pylint: disable=relative-import

"""Read configureation and generate terraform configuration JSON file"""

from __future__ import print_function
import logging
import argparse

from common.terraform_config import TerraformConfiguration
from common.log import setup_logging

LOG = logging.getLogger(__name__)


def parse_command_line():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Generate terraform environment from configuration file')
    parser.add_argument(
        '-d',
        '--debug',
        action='store_true',
        help='enable debug output')
    parser.add_argument(
        '--log-file',
        help='path to log file')
    parser.add_argument(
        '--out-file',
        default='cluster.json',
        help='name of the output JSON file')
    return parser.parse_args()


def main():
    """Main function."""
    args = parse_command_line()
    setup_logging(args.debug, args.log_file)  # pylint: disable=no-member

    tf_config = TerraformConfiguration()

    # write to file
    tf_config.to_json(file_name=args.out_file)  # pylint: disable=no-member
    return True

if __name__ == '__main__':
    main()
