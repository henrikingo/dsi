#!/usr/bin/env python2.7
""" Script for removing overrides based on tickets."""

import sys
import argparse
import logging

from evergreen.override import Override

LOGGER = None
WARNER = None


def main(args):
    """Delete unneeded overrides."""

    global LOGGER, WARNER  # pylint: disable=global-statement
    parser = argparse.ArgumentParser(description='Update performance test overrides. The '
                                     'parameters used for specifying project/variants/tasks/tests '
                                     'are considered regular expression patterns. To express '
                                     'an exact match, enclose the terms in ^ and $')

    parser.add_argument('ticket', help='Remove overrides related to this ticket')
    parser.add_argument(
        '-n',
        '--reference',
        help='The Git commit hash (min. length 7 prefix) or tag from which to pull '
        'data from as an override reference')
    parser.add_argument('-f', '--override-file', help='The path to the override file to update')
    parser.add_argument(
        '-d',
        '--destination-file',
        default='override.json',
        help='The path to write the updated override')
    parser.add_argument('-r', '--rule', default='all', help='The rule to check.')
    parser.add_argument('-k', '--tasks', default='.*', help='The task or tasks to update')
    parser.add_argument(
        '-p',
        '--project',
        default='performance',
        help='The Evergreen project for which to generate overrides')
    parser.add_argument(
        '-c',
        '--config',
        help='The path to your evergreen & github auth configuration file. '
        '(See /example_config.yml for formatting.)')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose output')

    # Parse the arguments and initialize the logging output
    args = parser.parse_args(args)
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

    override_obj = Override(
        args.project,
        override_info=args.override_file,
        config_file=args.config,
        reference=args.reference,
        verbose=args.verbose)
    rule = args.rule
    if rule == 'all':
        rules = ['reference', 'ndays', 'threshold']
    else:
        rules = [rule]
    override_obj.delete_overrides_by_ticket(args.ticket, rules, tasks=args.tasks.split('|'))

    # Dump the new file as JSON
    LOGGER.info('Saving output to %s', args.destination_file)
    override_obj.save_to_file(args.destination_file)


if __name__ == '__main__':
    main(sys.argv[1:])
