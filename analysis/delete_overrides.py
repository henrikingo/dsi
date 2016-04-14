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

""" Script for removing overrides based on tickets."""

# pylint: disable=logging-format-interpolation

import sys
import argparse
import logging


from evergreen import override


def main():
    '''
    Delete unneeded overrides.
    '''

    global logger, warner # pylint: disable=invalid-name,global-variable-undefined
    parser = argparse.ArgumentParser(description='Update performance test overrides. The \
        parameters used for specifying project/variants/tasks/tests are considered regular \
        expression patterns. To express exact match, enclose the terms in ^ and $')

    parser.add_argument('ticket',
                        help='Remove overrides releated to this ticket')
    parser.add_argument('-f',
                        '--override-file',
                        help='The path to the override file to update')
    parser.add_argument('-d',
                        '--destination-file',
                        default='override.json',
                        help='The path to write the updated override')
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

    logger = logging.getLogger('override.update.information')
    logger.addHandler(logging.StreamHandler(sys.stdout))
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)

    ovr = override.Override(args.override_file)
    if args.rule == 'all':
        # Check reference, ndays, and threshold
        ovr.delete_overrides_by_ticket(args.ticket, 'reference')
        ovr.delete_overrides_by_ticket(args.ticket, 'ndays')
        ovr.delete_overrides_by_ticket(args.ticket, 'threshold')
    else:
        ovr.delete_overrides_by_ticket(args.ticket, args.rule)

    # Dump the new file as JSON
    logger.info('Saving output to {destination}'.format(destination=args.destination_file))
    ovr.save_to_file(args.destination_file)

if __name__ == '__main__':
    main()
