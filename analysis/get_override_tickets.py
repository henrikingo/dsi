#!/usr/bin/env python

# Copyright 2016 MongoDB Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Runner script for checking tickets in overrides."""

from __future__ import print_function
import sys
import argparse
import logging

from evergreen import override

def main():
    '''
    Check overrides for tickets
    '''

    global logger, warner # pylint: disable=invalid-name,global-variable-undefined
    parser = argparse.ArgumentParser(description='Check override file for tickets')

    parser.add_argument('-p',
                        '--project',
                        default='performance',
                        help='The Evergreen project to check')
    parser.add_argument('-v',
                        '--variants',
                        default='.*',
                        help='The build variant or variants to check; defaults to all')
    parser.add_argument('-k',
                        '--tasks',
                        default='.*',
                        help='The task or tasks to check')
    parser.add_argument('-f',
                        '--override-file',
                        help='The path to the override file to update')
    parser.add_argument('--verbose',
                        action='store_true',
                        help='Enable verbose output')
    parser.add_argument('-r',
                        '--rule',
                        default='all',
                        help='The rule to check')

    # Parse the arguments and initialize the logging output
    args = parser.parse_args()
    warner = logging.getLogger('override.update.warnings')
    err_handler = logging.StreamHandler(sys.stderr)
    err_handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
    warner.addHandler(err_handler)

    logger = logging.getLogger('override.override.information')
    logger.addHandler(logging.StreamHandler(sys.stdout))
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)

    ovr = override.Override(args.override_file)
    # Check if we should be checking all rules
    if args.rule == 'all':
        # Check reference, ndays, and threshold
        tickets = ovr.get_tickets('reference')
        tickets.update(ovr.get_tickets('ndays'))
        tickets.update(ovr.get_tickets('threshold'))
    else:
        tickets = ovr.get_tickets(args.rule)

    for ticket in tickets:
        print(ticket)

if __name__ == '__main__':
    main()
