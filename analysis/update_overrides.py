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

import sys
import argparse
import json
import logging
import os

import requests

import evergreen
from evergreen import evergreen, helpers, override
from evergreen.history import History

def update_override_thresholds(project, reference, ticket, threshold,
                               thread_threshold, ovr=None, evg=None,
                               variants=None, tasks=None, tests=None):
    '''
    Update a performance threshold level override

    :param str project: The project name in Evergreen
    :param str reference: The Git SHA1 or tag to use as a reference
    :param str ticket: The JIRA ticket associated with this override
    :param float thresold: The new threshold to use
    :param float thread_thresold: The new thread threshold to use
    :param Override.override ovr: (optional) The base override to update
    :param evergreen.Client evg: (optional) A handle to an Evergreen server
    :param list[str] variants: (optional) The build variant or variants to override
    :param list[str] tasks: (optional) The task or tasks to override
    :param list[str] tests: (optional) The test or tests to override

    '''
    global logger, warner
    if not evg:
        evg = evergreen.Client()
    if not ovr:
        ovr = override.Override(None)

    # This part is a giant hack copied from update_override. All I
    # really want is the list of variants and task

    # Are we comparing against a tag or a commit?
    try:
        # Attempt to query Evergreen by treating this reference as a Git commit
        evg.build_variants_from_git_commit(project, reference).next()
        commit = reference
        compare_to_commit = True
        logger.debug('Treating reference point "{commit}" as a Git commit'.format(commit=reference))
    except requests.HTTPError:
        # Evergreen could not find a commit, so fall back to using a tag

        # Find the latest builds in Evergreen, get the oldest result in the history, then pull out
        # the Git commit

        commit = evg.get_recent_revisions(project, max_results=30)[-1]['revision']
        compare_to_commit = False
        logger.debug('Treating reference point "{tag}" as a tagged baseline'.format(tag=reference))
        logger.debug(
            'Getting {proj} project information from commit {commit}'.format(proj=project,
                                                                             commit=commit))

    build_variants_applied = set()
    tasks_applied = set()
    tests_applied = set()
    summary = {}

    new_override = {'threshold': threshold,
                    'thread_threshold': thread_threshold}


    # Find the build variants for the mongo-perf project at this Git commit
    for build_variant_name, build_variant_id in evg.build_variants_from_git_commit(project, commit):

        match = helpers.matches_any(build_variant_name, variants)
        if not match:
            logger.debug('Skipping build variant: {0}'.format(build_variant_name))
            continue

        build_variants_applied.add(match)
        summary[build_variant_name] = {}
        logger.debug('Processing build variant: {0}'.format(build_variant_name))

        # Find the tasks in this build variant that we're interested in
        for task_name, task_id in evg.tasks_from_build_variant(build_variant_id):
            if 'compile' in task_name:
                logger.debug('\tSkipping compilation stage')
                continue

            match = helpers.matches_any(task_name, tasks)
            if not match:
                logger.debug('\tSkipping task: {0}'.format(task_name))
                continue

            tasks_applied.add(match)
            summary[build_variant_name][task_name] = []
            logger.debug('\tProcessing task: {0}'.format(task_name))

            # Cycle through the names of the tests in this task
            for test_name, _ in evg.tests_from_task(task_id):
                match = helpers.matches_any(test_name, tests)
                if not match:
                    logger.debug('\t\tSkipping test: {0}'.format(test_name))
                    continue

                tests_applied.add(match)
                summary[build_variant_name][task_name].append(test_name)
                logger.debug('\t\tProcessing test: {0}'.format(test_name))

                # Finally, update the old override rule
                ovr.update_test(build_variant_name, test_name, 'threshold', new_override, ticket)

    # Sanity checks!
    for unused_test in [test for test in tests if test not in tests_applied]:
        warner.warn('Pattern not applied for tests: {0}'.format(unused_test))

    for unused_task in [task for task in tasks if task not in tasks_applied]:
        warner.warn('Pattern not applied for tasks: {0}'.format(unused_task))

    for unused_variant in [variant for variant in variants if variant not in build_variants_applied]:
        warner.warn('Pattern not applied for build variants: {0}'.format(unused_variant))

    # Review and print a summary of what's been accomplished
    if not summary:
        warner.critical('No overrides have changed whatsoever')
    else:
        for variant in summary.keys():
            if not summary[variant]:
                warner.warn('No tasks under the build variant {0} were overridden'.format(variant))
            for task in summary[variant].keys():
                if not summary[variant][task]:
                    warner.warn('No tests under the task {0}.{1} were overridden'.format(variant, task))

        logger.info('The following tests have been overridden:')
        logger.info(json.dumps(summary, indent=2, separators=[',', ': '], sort_keys=True))

    logger.debug('Override update complete.')
    return ovr



def update_override(project, reference, ticket, rule="reference", ovr=None, evg=None, variants=None, tasks=None, tests=None):
    """Update a performance reference override.

    :param str project: The project name in Evergreen
    :param str reference: The Git SHA1 or tag to use as a reference
    :param str ticket: The JIRA ticket associated with this override
    :param str rule: (default="reference") The rule to override (reference or ndays)
    :param Override.override ovr: (optional) The base override to update
    :param evergreen.Client evg: (optional) A handle to an Evergreen server
    :param list[str] variants: (optional) The build variant or variants to override
    :param list[str] tasks: (optional) The task or tasks to override
    :param list[str] tests: (optional) The test or tests to override
    """
    global logger, warner
    if not evg:
        evg = evergreen.Client()
    if not ovr:
        ovr = override.Override(None)

    # Are we comparing against a tag or a commit?
    try:
        # Attempt to query Evergreen by treating this reference as a Git commit
        evg.build_variants_from_git_commit(project, reference).next()
        commit = reference
        compare_to_commit = True
        logger.debug('Treating reference point "{commit}" as a Git commit'.format(commit=reference))
    except requests.HTTPError:
        # Evergreen could not find a commit, so fall back to using a tag
        # Find the latest builds in Evergreen, get the oldest result in the history, then pull out the Git commit
        commit = evg.get_recent_revisions(project, max_results=30)[-1]['revision']
        compare_to_commit = False
        logger.debug('Treating reference point "{tag}" as a tagged baseline'.format(tag=reference))
        logger.debug('Getting {proj} project information from commit {commit}'.format(proj=project, commit=commit))

    build_variants_applied = set()
    tasks_applied = set()
    tests_applied = set()
    summary = {}

    # Find the build variants for the mongo-perf project at this Git commit
    for build_variant_name, build_variant_id in evg.build_variants_from_git_commit(project, commit):

        match = helpers.matches_any(build_variant_name, variants)
        if not match:
            logger.debug('Skipping build variant: {0}'.format(build_variant_name))
            continue

        build_variants_applied.add(match)
        summary[build_variant_name] = {}
        logger.debug('Processing build variant: {0}'.format(build_variant_name))

        # Find the tasks in this build variant that we're interested in
        for task_name, task_id in evg.tasks_from_build_variant(build_variant_id):
            if 'compile' in task_name:
                logger.debug('\tSkipping compilation stage')
                continue

            match = helpers.matches_any(task_name, tasks)
            if not match:
                logger.debug('\tSkipping task: {0}'.format(task_name))
                continue

            tasks_applied.add(match)
            summary[build_variant_name][task_name] = []
            logger.debug('\tProcessing task: {0}'.format(task_name))

            # Get the performance data for this task
            if compare_to_commit:
                task_data = evg.query_mongo_perf_task_history(task_name, task_id)
            else:
                task_data = evg.query_mongo_perf_task_tags(task_name, task_id)

            # Examine the history data
            history = History(task_data)

            # Cycle through the names of the tests in this task
            for test_name, _ in evg.tests_from_task(task_id):
                match = helpers.matches_any(test_name, tests)
                if not match:
                    logger.debug('\t\tSkipping test: {0}'.format(test_name))
                    continue

                tests_applied.add(match)
                summary[build_variant_name][task_name].append(test_name)
                logger.debug('\t\tProcessing test: {0}'.format(test_name))

                # Get the reference data we want to use as the override value
                if compare_to_commit:
                    test_reference = history.series_at_revision(test_name, reference)
                else:
                    test_reference = history.series_at_tag(test_name, reference)

                if not test_reference:
                    raise evergreen.Empty(
                        'No data for {bv}.{task}.{test} at reference {ref}'.format(bv=build_variant_name,
                                                                                   task=task_name,
                                                                                   test=test_name,
                                                                                   ref=reference))

                # Finally, update the old override rule
                ovr.update_test(build_variant_name, test_name, rule, test_reference, ticket)

    # Sanity checks!
    for unused_test in [test for test in tests if test not in tests_applied]:
        warner.warn('Pattern not applied for tests: {0}'.format(unused_test))

    for unused_task in [task for task in tasks if task not in tasks_applied]:
        warner.warn('Pattern not applied for tasks: {0}'.format(unused_task))

    for unused_variant in [variant for variant in variants if variant not in build_variants_applied]:
        warner.warn('Pattern not applied for build variants: {0}'.format(unused_variant))

    # Review and print a summary of what's been accomplished
    if not summary:
        warner.critical('No overrides have changed whatsoever')
    else:
        for variant in summary.keys():
            if not summary[variant]:
                warner.warn('No tasks under the build variant {0} were overridden'.format(variant))
            for task in summary[variant].keys():
                if not summary[variant][task]:
                    warner.warn('No tests under the task {0}.{1} were overridden'.format(variant, task))

        logger.info('The following tests have been overridden:')
        logger.info(json.dumps(summary, indent=2, separators=[',', ': '], sort_keys=True))

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
            history = History(evg.query_task_perf_history(task_id))

            # Loop through the names of tests
            for test_name, _ in evg.tests_from_task(task_id):
                if not helpers.matches_any(test_name, tests):
                    print('Skipping {test}'.format(test=test_name))

                data = history.series_at_revision(test_name, revision)

def main():
    '''
    Update the overrides
    '''

    global logger, warner
    parser = argparse.ArgumentParser(description='Update performance test overrides. The \
        parameters used for specifying project/variants/tasks/tests are considered regular \
        expression patterns. To express exact match, enclose the terms in ^ and $')

    parser.add_argument('reference',
                        help='The Git commit or tag from which to pull data from as an override reference')
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
                        default=os.path.expanduser('~/.evergreen.yml'),
                        help='The path to your .evergreen.yml configuration')
    parser.add_argument('--verbose',
                        action='store_true',
                        help='Enable verbose output')
    parser.add_argument('-n',
                        '--ndays',
                        action='store_true',
                        help='Override ndays instead of baseline/reference')
    parser.add_argument('--threshold',
                        help='New default threshold. Must be used in tandem with'\
                        '--thread-threshold')
    parser.add_argument('--thread-threshold',
                        help='New thread threshold. Must be used in tandem with --threshold')

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

    output_override = None
    # Make sure that if threshold is set, so is thread-threshold. If so, set variable
    # use_threshold_overrides
    use_threshold_overrides = False
    if args.threshold:
        if args.thread_threshold:
            use_threshold_overrides = True
            logger.info("Updating threshold overrides")
        else:
            warner.critical('--threshold set on command line, but --thread-threshold is not')
    elif args.thread_threshold:
        warner.critical('--thread-threshold set on command line, but --threshold is not.')

    if use_threshold_overrides:
        output_override = update_override_thresholds(args.project,
                                                     args.reference, args.ticket,
                                                     float(args.threshold),
                                                     float(args.thread_threshold),
                                                     ovr=override.Override(args.override_file),
                                                     evg=evergreen.Client(args.config),
                                                     variants=args.variants.split('|'),
                                                     tasks=args.tasks.split('|'),
                                                     tests=args.tests.split('|'))
    else:
        if args.ndays:
            rule = 'ndays'
        else:
            rule = 'reference'

        # Pass the rest of the command-line arguments
        output_override = update_override(args.project, args.reference,
                                          args.ticket, rule=rule,
                                          ovr=override.Override(args.override_file),
                                          evg=evergreen.Client(args.config),
                                          variants=args.variants.split('|'),
                                          tasks=args.tasks.split('|'),
                                          tests=args.tests.split('|'))

    # Dump the new file as JSON
    logger.info('Saving output to {destination}'.format(destination=args.destination_file))
    output_override.save_to_file(args.destination_file)

if __name__ == '__main__':
    main()
