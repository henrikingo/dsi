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

"""Module for manipulating override files."""

from __future__ import print_function
import json
import sys

import evergreen
import helpers
import regression

# TODO: have update() accept a symbolic integer


ALL = 0
"""Indicates that all tests should be overridden."""


FAILED = 1
"""Indicates that all failed tests should be overridden."""


class Override(object):
    """Represents an override for a performance test."""
    def __init__(self, initializer):
        """Create a new override.

        :param initializer: The starting point for building overrides
        """
        if initializer is None:
            self.overrides = {
                'ndays': {},
                'reference': {}
            }
        elif isinstance(initializer, str):
            with open(initializer) as fd:
                self.overrides = json.load(fd)
        elif isinstance(initializer, dict):
            self.overrides = initializer
        else:
            raise TypeError('initializer must be a file, filename or dictionary')

    def get_overrides_by_ticket(self, ticket):
        """Get the overrides created by a given ticket.

        :param str ticket: The ID of a JIRA ticket (e.g. PERF-226)
        :rtype: list[dict]
        """
        # TODO implement this
        pass

    def delete_overrides_by_ticket(self, ticket):
        """Remove the overrides created by a given ticket.

        :param str ticket: The ID of a JIRA ticket (e.g. SERVER-20123)
        """
        # TODO implement this
        pass

    def save_to_file(self, file_or_filename):
        """Saves this override to a JSON file.

        :param file|str file_or_filename: A file or filename destination to save to
        """
        if isinstance(file_or_filename, str):
            with open(file_or_filename, 'w') as fd:
                json.dump(self.overrides, fd, file_or_filename, indent=4, separators=[',', ':'], sort_keys=True)
        elif isinstance(file_or_filename, file):
            json.dump(self.overrides, file_or_filename, indent=4, separators=[',', ':'], sort_keys=True)
        else:
            raise TypeError('Argument must be a file or filename')

    def update(self, revision_id, tag, ticket=None, evg_url=None, variants=None, tasks=None, tests=None, **kwargs):
        """Update this override with additional test information.

        :param str revision_id: The Evergreen ID of the revision
        :param str tag: The tag to compare against (e.g. '3.1.9-Baseline')
        :param str ticket: The JIRA ticket associated with this override
        :param str evg_url: (optional) The base URL to an Evergreen instance
        :param list[str] variants: (optional) Override only these build variants. Must be the display name
        :param list[str] tasks: (optional) Override only these tasks. Must be a display name
        :param list[str] tests: (optional) Override only these tests. Must be a display name
        :return:
        """
        if not evg_url:
            evg_url = evergreen.DEFAULT_EVERGREEN_URL
        evg = evergreen.EvergreenClient(evg_url)

        # Begin examining the project structure on Evergreen
        all_variants = sorted(evg.get_build_variant_names_from_revision_id(revision_id))
        all_variant_ids = sorted(evg.get_build_variants_from_revision_id(revision_id))
        if not all_variant_ids or not all_variants:
            raise evergreen.EvergreenError('Could not find buildvariant information for this revision')

        for variant, variant_id in zip(all_variants, all_variant_ids):
            # TODO: special cases
            if 'compare' in variant:
                continue

            if not helpers.matches_any(variant, variants):
                # This is not one of the build variants we want.
                print('Skipping {variant}'.format(variant=variant))
                continue
            else:
                print('Processing buildvariant: {variant}'.format(variant=variant))

            # Find the tasks associated with this build variant
            task_info = evg.get_tasks_from_build_variant(variant_id)
            all_tasks = sorted(task_info.keys())
            variant_data = []

            # Obtain all of the performance data for each task (which includes all sub-tests)
            for task in all_tasks:
                # TODO: special cases
                if 'compile' in task:
                    continue

                if not helpers.matches_any(task, tasks):
                    # This is not one of the tasks specified.
                    print('Skipping task: {task}'.format(task=task))
                    continue
                else:
                    print('Processing task: {task}'.format(task=task))

                # Find the Evergreen ID for this task
                # TODO This must be pulled out as a method of EvergreenClient()
                task_id = task_info[task]['task_id']
                data = helpers.get_as_json('{base_url}/api/2/task/{task_id}/json/tags/{task_name}/perf'.format(
                    base_url=evg_url, task_id=task_id, task_name=task))
                variant_data.extend(data)

                # Get the history data
                tag_history = regression.History(variant_data)

                # Get the list of all test names
                all_tests = evg.get_test_names_from_task(task_id)

                for test in all_tests:
                    if not helpers.matches_any(test, tests):
                        # This is not one of the tests we want.
                        # TODO emit a log at the debug level that this is skipped. Otherwise, it's too verbose
                        continue
                    else:
                        print('Overriding test: {test}'.format(test=test))

                    test_reference = tag_history.seriesAtTag(test, tag)
                    if not test_reference:
                        raise evergreen.EvergreenError(
                            'There is no tag history for {bv}.{task}.{test} at tag {tag}'.format(bv=variant,
                                                                                                 task=task,
                                                                                                 test=test,
                                                                                                 tag=tag))
                    # Perform the actual override and attach a ticket number
                    self.overrides[variant]['reference'][test] = test_reference
                    if ticket:
                        self.overrides[variant]['reference'][test]['ticket'] = ticket

        print('Override update complete.')

