#!/usr/bin/env python2.7
# pylint: disable=relative-import

"""
    Read configureation and generate terraform configuration JSON file
    This program will read from stdin, pipe from terraform output, and
    generate infrastructure.out.yml file for the cluster in the current
    directory.
"""

from __future__ import print_function
import logging
import argparse

from common.log import setup_logging
from common.terraform_output_parser import TerraformOutputParser

LOG = logging.getLogger(__name__)


def parse_command_line():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Generate infrastructure.out.yml for the cluster')
    parser.add_argument(
        '-d',
        '--debug',
        action='store_true',
        help='enable debug output')
    parser.add_argument(
        '--log-file',
        help='path to log file')
    return parser.parse_args()


def main():
    """The main function"""
    args = parse_command_line()
    setup_logging(args.debug, args.log_file)  # pylint: disable=no-member

    tf_parser = TerraformOutputParser()
    tf_parser.write_output_files()

if __name__ == '__main__':
    main()
