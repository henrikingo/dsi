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

"""Module to track state dependencies during an override file update operation,
excluding a threshold update
"""

import json
import logging
import sys

import requests

from evergreen import evergreen_client
from evergreen import helpers
from evergreen import override
from evergreen.history import History

LOGGER = None
WARNER = None


class UpdateOverride(object):  # pylint: disable=too-many-instance-attributes,too-few-public-methods
    """Base class for updating override files. Default functionality does not account for
    threshold overrides.
    """

    def __init__(  # pylint: disable=too-many-statements,too-many-arguments
            self, project, reference, variants, tasks, tests,
            override_file, config_file=None, rule='reference', ticket=None, verbose=False):
        """
        :param str project: The project name in Evergreen
        :param str reference: The Git SHA1 or tag to use as a reference
        :param list[str] variants: The build variant or var2iants to override
        :param list[str] tasks: The task or tasks to override
        :param list[str] tests: The test or tests to override
        :param str override_file: The file to write to after an override update
        :param str config_file: For testing on Evergreen, a config with Evergreen & Github creds
        :param str rule: (default="reference") The rule to override (reference or ndays)
        :param str ticket: The JIRA ticket associated with this override
        """
        global LOGGER, WARNER  # pylint: disable=global-statement
        WARNER = logging.getLogger('override.update.warnings')
        LOGGER = logging.getLogger('override.update.information')

        if verbose:
            LOGGER.setLevel(logging.DEBUG)
        else:
            LOGGER.setLevel(logging.INFO)

        # parse the config file
        creds = None
        if config_file:
            creds = helpers.file_as_yaml(config_file)
        else:
            creds = helpers.create_credentials_config()

        self.evg = evergreen_client.Client(creds['evergreen'])
        self.ovr = override.Override(override_file)

        self.project = project
        self.variants = variants
        self.tasks = tasks
        self.tests = tests

        self.build_variants_applied = set()
        self.tasks_applied = set()
        self.tests_applied = set()
        self.summary = {}

        self.rule = rule
        self.ticket = ticket

        # This part is a giant hack copied from update_override. All I
        # really want is the list of variants and task

        # Are we comparing against a tag or a commit?
        try:
            # Attempt to query Evergreen by treating this reference as a Git commit
            self.commit = helpers.get_full_git_commit_hash(reference, creds['github']['token'])
            self.compare_to_commit = True
            LOGGER.debug('Treating reference point "{commit}" as a Git commit'.format(
                commit=self.commit))
        except KeyError:
            LOGGER.debug('Unable to retrieve a valid github token from ~/.gitconfig')
            sys.exit(0)
        except requests.HTTPError:
            # Evergreen could not find a commit, so fall back to using a tag

            # Find the latest builds in Evergreen, get the oldest result in the history,
            # then pull out the Git commit
            self.commit = reference
            self.compare_to_commit = False
            LOGGER.debug('Treating reference point "{tag}" as a tagged baseline'.format(
                tag=self.commit))
            LOGGER.debug(
                'Getting {proj} project information from commit {commit}'.format(
                    proj=project, commit=self.commit))

    def _final_checks_override(self):
        # Sanity checks!
        for unused_test in [test for test in self.tests if test not in self.tests_applied]:
            WARNER.warn('Pattern not applied for tests: {0}'.format(unused_test))

        for unused_task in [task for task in self.tasks if task not in self.tasks_applied]:
            WARNER.warn('Pattern not applied for tasks: {0}'.format(unused_task))

        for unused_variant in [variant for variant in self.variants
                               if variant not in self.build_variants_applied]:
            WARNER.warn('Pattern not applied for build variants: {0}'.format(unused_variant))

        # Review and print a summary of what's been accomplished
        if len(self.summary) == 0:
            WARNER.critical('No overrides have changed.')
        else:
            for variant in self.summary.keys():
                if not self.summary[variant]:
                    WARNER.warn('No tasks under the build variant {0} were overridden'.format(
                        variant))
                for task in self.summary[variant].keys():
                    if not self.summary[variant][task]:
                        WARNER.warn('No tests under the task {0}.{1} were overridden'.format(
                            variant, task))
            LOGGER.info('The following tests have been overridden:')
            LOGGER.info(json.dumps(self.summary, indent=2, separators=[',', ': '], sort_keys=True))

        LOGGER.debug('Override update complete.')

    def update_override(self):
        """Update a performance reference override."""
        # Find the build variants for the mongo-perf project at this Git commit
        for build_variant_name, build_variant_id in self.evg.build_variants_from_git_commit(
                self.project, self.commit):
            match = helpers.matches_any(build_variant_name, self.variants)
            if not match:
                LOGGER.debug('Skipping build variant: {0}'.format(build_variant_name))
                continue

            self.build_variants_applied.add(match)
            self.summary[build_variant_name] = {}
            LOGGER.debug('Processing build variant: {0}'.format(build_variant_name))

            # Find the tasks in this build variant that we're interested in
            for task_name, task_id in self.evg.tasks_from_build_variant(build_variant_id):
                if 'compile' in task_name:
                    LOGGER.debug('\tSkipping compilation stage')
                    continue

                match = helpers.matches_any(task_name, self.tasks)
                if not match:
                    LOGGER.debug('\tSkipping task: {0}'.format(task_name))
                    continue

                self.tasks_applied.add(match)
                self.summary[build_variant_name][task_name] = []
                LOGGER.debug('\tProcessing task: {0}'.format(task_name))

                # Get the performance data for this task
                if self.compare_to_commit:
                    task_data = self.evg.query_mongo_perf_task_history(task_name, task_id)
                else:
                    task_data = self.evg.query_mongo_perf_task_tags(task_name, task_id)

                # Examine the history data
                history = History(task_data)

                # Cycle through the names of the tests in this task
                for test_name, _ in self.evg.tests_from_task(task_id):
                    match = helpers.matches_any(test_name, self.tests)
                    if not match:
                        LOGGER.debug('\t\tSkipping test: {0}'.format(test_name))
                        continue

                    self.tests_applied.add(match)
                    self.summary[build_variant_name][task_name].append(test_name)
                    LOGGER.debug('\t\tProcessing test: {0}'.format(test_name))

                    # Get the reference data we want to use as the override value
                    if self.compare_to_commit:
                        test_reference = history.series_at_revision(test_name, self.commit)
                    else:
                        test_reference = history.series_at_tag(test_name, self.commit)

                    if not test_reference:
                        raise evergreen_client.Empty(
                            'No data for {bv}.{task}.{test} at reference {ref}'.format(
                                bv=build_variant_name,
                                task=task_name,
                                test=test_name,
                                ref=self.commit)
                            )

                    # Finally, update the old override rule
                    self.ovr.update_test(
                        build_variant_name, test_name, self.rule, test_reference, self.ticket)
        self._final_checks_override()
