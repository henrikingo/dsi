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


class NotYetImplemented(RuntimeError):
    """Indicates that this function has yet to be implemented."""
    pass


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
        raise NotYetImplemented()

    def delete_overrides_by_ticket(self, ticket):
        """Remove the overrides created by a given ticket.

        :param str ticket: The ID of a JIRA ticket (e.g. SERVER-20123)
        """
        # TODO implement this
        raise NotYetImplemented()

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

    def update_performance_reference(self, revision, tag, ticket, evg=None, variants=None, tasks=None, tests=None):
        """Update a performance reference override.

        :param str revision: The Git SHA1 of the desired revision
        :param str tag: The tag to compare against (e.g. '3.1.9-Baseline')
        :param str ticket: The JIRA ticket associated with this override
        :param evergreen.Client evg: (optional) A handle to an Evergreen server
        :param str|list[str] variants: (optional) The build variant or variants to override
        :param str|list[str] tasks: (optional) The task or tasks to override
        :param str|list[str] tests: (optional) The test or tests to override
        """
        if not evg:
            evg = evergreen.Client()

        for build_variant_name, build_variant_id in evg.build_variants_from_git_commit('performance', revision):
            if not helpers.matches_any(build_variant_name, variants):
                print('Skipping build variant {}'.format(build_variant_name))
                continue

            # TODO: special case
            if 'compare' in build_variant_name:
                continue

            print('Processing build variant: {}'.format(build_variant_name))
            variant_data = []

            for task_name, task_id in evg.tasks_from_build_variant(build_variant_id):
                if not helpers.matches_any(task_name, tasks):
                    print('Skipping task {}'.format(task_name))
                    continue

                # Get the performance data for this task
                data = evg.query_task_perf_tags(task_name, task_id)
                variant_data.extend(data)

                # Examine the history data
                tag_history = regression.History(variant_data)

                for test_name, _ in evg.tests_from_task(task_id):
                    if not helpers.matches_any(test_name, tests):
                        continue

                    print('Processing test: {}'.format(test_name))
                    test_reference = tag_history.seriesAtTag(test_name, tag)
                    if not test_reference:
                        raise evergreen.Empty(
                            'No tag history for {bv}.{task}.{test} at tag {tag}'.format(bv=build_variant_name,
                                                                                        task=task_name,
                                                                                        test=test_name,
                                                                                        tag=tag))
                    # Perform the actual override, attaching a ticket number
                    reference = self.overrides[build_variant_name]['reference']
                    reference[test_name] = test_reference
                    try:
                        reference[test_name]['ticket'].append(ticket)
                    except KeyError:
                        reference[test_name]['ticket'] = [ticket]
                if not test_name:
                    raise evergreen.Empty('No tests found for task {}'.format(task_name))
            if not task_id:
                raise evergreen.Empty('No tasks found for build variant {}'.format(build_variant_name))
        if not build_variant_id:
            raise evergreen.Empty('No builds for commit {} in performance'.format(revision))

        print('Override update complete.')

