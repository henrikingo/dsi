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
import json
import logging
import os
import sys

import evergreen
import helpers
import override
import regression


def update_performance_reference(revision, tag, ticket, ovr=None, evg=None, variants=None, tasks=None, tests=None):
    """Update a performance reference override.

    :param str revision: The Git SHA1 of the desired revision
    :param str tag: The tag to compare against (e.g. '3.1.9-Baseline')
    :param str ticket: The JIRA ticket associated with this override
    :param dict|Override.override ovr: (optional) The base override to update
    :param evergreen.Client evg: (optional) A handle to an Evergreen server
    :param list[str] variants: (optional) The build variant or variants to override
    :param list[str] tasks: (optional) The task or tasks to override
    :param list[str] tests: (optional) The test or tests to override
    """
    global logger, warner
    if not evg:
        logger.debug('Using default Evergreen client with no authentication information')
        evg = evergreen.Client()
    if not ovr:
        logger.debug('Using default empty override structure')
        ovr = override.Override()

    build_variants_applied = set()
    tasks_applied = set()
    tests_applied = set()
    summary = {}

    # Cycle through each build variant, task, and test. Update overrides as we find matching items
    for build_variant_name, build_variant_id in evg.build_variants_from_git_commit('performance', revision):
        # TODO: special case
        if 'compare' in build_variant_name:
            logger.debug('Skipping compilation stage')
            continue

        match = helpers.matches_any(build_variant_name, variants)
        if not match:
            logger.debug('Skipping build variant: {}'.format(build_variant_name))
            continue

        build_variants_applied.add(match)
        summary[build_variant_name] = {}
        logger.debug('Processing build variant: {}'.format(build_variant_name))

        for task_name, task_id in evg.tasks_from_build_variant(build_variant_id):
            match = helpers.matches_any(task_name, tasks)
            if not match:
                logger.debug('\tSkipping task: {}'.format(task_name))
                continue

            tasks_applied.add(match)
            summary[build_variant_name][task_name] = []
            logger.debug('\tProcessing task: {}'.format(task_name))

            # Get the performance data for this task
            task_data = evg.query_task_perf_tags(task_name, task_id)

            # Examine the history data
            tag_history = regression.History(task_data)

            for test_name, _ in evg.tests_from_task(task_id):
                match = helpers.matches_any(test_name, tests)
                if not match:
                    logger.debug('\t\tSkipping test: {}'.format(test_name))
                    continue

                tests_applied.add(match)
                summary[build_variant_name][task_name].append(test_name)
                logger.debug('\t\tProcessing test: {}'.format(test_name))

                # Find the reference data for this test
                test_reference = tag_history.seriesAtTag(test_name, tag)
                if not test_reference:
                    raise evergreen.Empty(
                        'No tag history for {bv}.{task}.{test} at tag {tag}'.format(bv=build_variant_name,
                                                                                    task=task_name,
                                                                                    test=test_name,
                                                                                    tag=tag))
                # Perform the actual override, attaching a ticket number
                reference = ovr.overrides[build_variant_name]['reference']
                reference[test_name] = test_reference
                try:
                    reference[test_name]['ticket'].append(ticket)
                except KeyError:
                    reference[test_name]['ticket'] = [ticket]

    # Sanity checks!
    for unused_test in [test for test in tests if test not in tests_applied]:
        warner.warn('Pattern not applied for tests: {}'.format(unused_test))

    for unused_task in [task for task in tasks if task not in tasks_applied]:
        warner.warn('Pattern not applied for tasks: {}'.format(unused_task))

    for unused_variant in [variant for variant in variants if variant not in build_variants_applied]:
        warner.warn('Pattern not applied for build variants: {}'.format(unused_variant))

    # Review and print a summary of what's been accomplished
    if not summary:
        warner.critical('No overrides have changed whatsoever')
    else:
        for variant in summary.keys():
            if not summary[variant]:
                warner.warn('No tasks under the build variant {} were overridden'.format(variant))
            for task in summary[variant].keys():
                if not summary[variant][task]:
                    warner.warn('No tests under the task {}.{} were overridden'.format(variant, task))

        logger.info('The following tests have been overridden:')
        logger.info(json.dumps(summary, indent=2, separators=[',', ': ']))

    logger.debug('Override update complete.')
    return ovr


def update_sysperf_ndays(self, revision, ticket, evg=None, variants=None, tasks=None, tests=None):
    """Update the 'ndays' reference information for the sys-perf project.

    :param str revision: The git commit to use as the new reference
    :param str ticket: The JIRA ticket associated with this override
    :param evergreen.Client evg: (optional) A handle to an Evergreen server
    :param str|list[str] variants: (optional) The variant or list of variants to override
    :param str|list[str] tasks: (optional) The task or list of tasks to override
    :param str|list[str] tests: (optional) The test or list of tests to override
    """
    if evg is None:
        evg = evergreen.Client()

    # Find the build variants for the sys-perf project for this Git commit
    for build_variant_name, build_variant_id in evg.build_variants_from_git_commit('sys-perf', revision):
        if not helpers.matches_any(build_variant_name, variants):
            print('Skipping {variant}'.format(variant=build_variant_name))

        # Find the tasks in this build variant that we're interested in
        for task_name, task_id in evg.tasks_from_build_variant(build_variant_id):
            if not helpers.matches_any(task_name, tasks):
                print('Skipping {task}'.format(task=task_name))

            # Find the historical data for this task
            history = regression.History(evg.query_task_perf_history(task_id))

            # Loop through the names of tests
            for test_name, _ in evg.tests_from_task(task_id):
                if not helpers.matches_any(test_name, tests):
                    print('Skipping {test}'.format(test=test_name))

                data = history.seriesAtRevision(test_name, revision)


if __name__ == '__main__':
    global logger, warner
    parser = argparse.ArgumentParser(prog='update-overrides',
                                     description='Update performance test overrides')
    parser.add_argument('reference',
                        help='The Git commit or tag from which to pull data from as an override reference')
    parser.add_argument('ticket',
                        help='The JIRA ticket associated with this override update')
    parser.add_argument('-v',
                        '--variants',
                        default='.*',
                        help='The build variant or variants to update')
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
                        default=os.path.join(os.path.expanduser('~'), '.evergreen.yml'),
                        help='The path to your .evergreen.yml configuration')
    parser.add_argument('--verbose',
                        action='store_true',
                        help='Enable verbose output')

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

    # Pass the rest of the command-line arguments
    output_override = update_performance_reference(args.reference,
                                                   args.ticket,
                                                   ovr=override.Override(args.override_file),
                                                   evg=evergreen.Client(args.config),
                                                   variants=args.variants.split('|'),
                                                   tasks=args.tasks.split('|'),
                                                   tests=args.tests.split('|'))

    # Dump the new file as JSON
    logger.debug('Saving output to {destination}'.format(destination=args.destination_file))
    output_override.save_to_file(args.destination_file)
