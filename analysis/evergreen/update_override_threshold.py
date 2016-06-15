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

"""Module to track state dependencies during an override file update threshold operation"""

import logging

from evergreen import helpers
from evergreen import update_override

LOGGER = None
WARNER = None


class UpdateOverrideThreshold(update_override.UpdateOverride):  # pylint: disable=too-few-public-methods
    """Update a performance threshold level override"""
    def __init__(  # pylint: disable=too-many-statements,too-many-arguments
            self, project, reference, variants, tasks, tests, threshold, thread_threshold,
            override_file, config_file=None, ticket=None, verbose=False):
        """
        :param str project: The project name in Evergreen
        :param str reference: The Git SHA1 or tag to use as a reference
        :param list[str] variants: The build variant or variants to override
        :param list[str] tasks: The task or tasks to override
        :param list[str] tests: The test or tests to override
        :param float threshold: The new threshold to use
        :param float thread_threshold: The new thread threshold to use
        :param str override_file: The file to write to after an override update
        :param str config_file: For testing on Evergreen, a config with Evergreen & Github creds
        :param str ticket: The JIRA ticket associated with this override
        """
        super(UpdateOverrideThreshold, self).__init__(project, reference, variants, tasks, tests,
                                                      override_file,
                                                      config_file=config_file,
                                                      rule='threshold',
                                                      ticket=ticket,
                                                      verbose=verbose)
        global LOGGER, WARNER  # pylint: disable=global-statement
        WARNER = logging.getLogger('override.update.warnings')
        LOGGER = logging.getLogger('override.update.information')

        if verbose:
            LOGGER.setLevel(logging.DEBUG)
        else:
            LOGGER.setLevel(logging.INFO)

        self.threshold = threshold
        self.thread_threshold = thread_threshold

    def update_override(self):
        new_override = {'threshold': self.threshold,
                        'thread_threshold': self.thread_threshold}

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

                # Cycle through the names of the tests in this task
                for test_name, _ in self.evg.tests_from_task(task_id):
                    match = helpers.matches_any(test_name, self.tests)
                    if not match:
                        LOGGER.debug('\t\tSkipping test: {0}'.format(test_name))
                        continue

                    self.tests_applied.add(match)
                    self.summary[build_variant_name][task_name].append(test_name)
                    LOGGER.debug('\t\tProcessing test: {0}'.format(test_name))

                    # Finally, update the old override rule
                    self.ovr.update_test(
                        build_variant_name, test_name, self.rule, new_override, self.ticket)
        self._final_checks_override()
