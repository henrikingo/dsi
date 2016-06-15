# Copyright 2015 MongoDB Inc.
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

"""Runner script for updating overrides."""
import argparse
import logging
import sys

from evergreen.update_override import UpdateOverride
from evergreen.update_override_threshold import UpdateOverrideThreshold

LOGGER = None
WARNER = None


def main():
    """Update the overrides"""
    global LOGGER, WARNER  # pylint: disable=global-statement
    parser = argparse.ArgumentParser(description='Update performance test overrides. The '
                                     'parameters used for specifying project/variants/tasks/tests'
                                     ' are considered regular expression patterns. To express'
                                     'exact match, enclose the terms in ^ and $')

    parser.add_argument('reference',
                        help='The Git commit prefix (min. length 7) or tag from which to pull '
                        'data from as an override reference')
    parser.add_argument('ticket',
                        help='The JIRA ticket associated with this override update')
    parser.add_argument('-p',
                        '--project',
                        default='performance',
                        help='The Evergreen project for which to generate overrides')
    parser.add_argument('-v',
                        '--variants',
                        default='.*',
                        help='The build variant or variants to update; defaults to all')
    parser.add_argument('-k',
                        '--tasks',
                        default='.*',
                        help='The task or tasks to update')
    parser.add_argument('-t',
                        '--tests',
                        default='.*',
                        help='The test or tests to update')
    parser.add_argument('-f',
                        '--override-file',
                        help='The path to the override file to update')
    parser.add_argument('-d',
                        '--destination-file',
                        default='override.json',
                        help='The path to write the updated override')
    parser.add_argument('-c',
                        '--config',
                        help='The path to your evergreen & github auth configuration file.'
                        ' (See testcases/example_update_override_config.yml for formatting.)')
    parser.add_argument('--verbose',
                        action='store_true',
                        help='Enable verbose output')
    parser.add_argument('-n',
                        '--ndays',
                        action='store_true',
                        help='Override ndays instead of baseline/reference')
    parser.add_argument('--threshold',
                        help='New default threshold. Must be used in tandem with'
                        '--thread-threshold')
    parser.add_argument('--thread-threshold',
                        help='New thread threshold. Must be used in tandem with --threshold')

    # Parse the arguments and initialize the logging output
    args = parser.parse_args()

    WARNER = logging.getLogger('override.update.warnings')
    err_handler = logging.StreamHandler(sys.stderr)
    err_handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
    WARNER.addHandler(err_handler)

    LOGGER = logging.getLogger('override.update.information')
    LOGGER.addHandler(logging.StreamHandler(sys.stdout))
    if args.verbose:
        LOGGER.setLevel(logging.DEBUG)
    else:
        LOGGER.setLevel(logging.INFO)

    update_obj = None
    # Make sure that if threshold is set, so is thread-threshold. If so, set variable
    # use_threshold_overrides
    use_threshold_overrides = False
    if args.threshold:
        if args.thread_threshold:
            use_threshold_overrides = True
            LOGGER.info("Updating threshold overrides")
        else:
            WARNER.critical('--threshold set on command line, but --thread-threshold is not')
    elif args.thread_threshold:
        WARNER.critical('--thread-threshold set on command line, but --threshold is not.')

    if use_threshold_overrides:
        update_obj = UpdateOverrideThreshold(args.project,
                                             args.reference,
                                             args.variants.split('|'),
                                             args.tasks.split('|'),
                                             args.tests.split('|'),
                                             float(args.threshold),
                                             float(args.thread_threshold),
                                             args.override_file,
                                             config_file=args.config,
                                             ticket=args.ticket,
                                             verbose=args.verbose)
        update_obj.update_override()
    else:
        if args.ndays:
            rule = 'ndays'
        else:
            rule = 'reference'
        update_obj = UpdateOverride(args.project,  # pylint: disable=redefined-variable-type
                                    args.reference,
                                    args.variants.split('|'),
                                    args.tasks.split('|'),
                                    args.tests.split('|'),
                                    args.override_file,
                                    config_file=args.config,
                                    rule=rule,
                                    ticket=args.ticket,
                                    verbose=args.verbose)

        update_obj.update_override()
    # Dump the new file as JSON
    LOGGER.info('Saving output to %s', args.destination_file)
    update_obj.ovr.save_to_file(args.destination_file)

if __name__ == '__main__':
    main()
