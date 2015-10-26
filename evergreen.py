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

"""Module for interacting with Evergreen."""

# TODO: Replace print statements with the logging module. In PyCharm, it doesn't seem to work with the console
# TODO: Code cleanup

from __future__ import print_function
import logging

import helpers

DEFAULT_EVERGREEN_URL = 'https://evergreen.mongodb.com'
"""The default Evergreen URL."""


class EvergreenError(Exception):
    """Generic class for Evergreen errors."""
    pass


class EvergreenClient(object):
    """Allows for interaction with an Evergreen server."""

    def __init__(self, base_url=None, verbose=True):
        """Create a new handle to an Evergreen server.

        :param base_url: (optional) The URL to the Evergreen server. If not specified, uses a reasonable default.
        """
        self.logger = logging.getLogger('evergreen')
        self.logger.level = logging.INFO if verbose else logging.WARNING
        self.base_url = base_url if base_url is not None else DEFAULT_EVERGREEN_URL

    def get_recent_revisions(self, project_name, max_results=10):
        """Get the most recent revisions for an Evergreen project.

        Valid project names include "performance" for the MongoDB Perf Project, "sys_perf" for System Performance, and
        so on.

        This method returns a list of dicts, where each dict describes the version and the various build variants
        underneath it:

            {
                'version_id': 'performance_30efc2300ad8740023ebb432723a1e662d16ef89',
                'author': 'David',
                'revision': '30efc2300ad8740023ebb432723a1e662d16ef89',
                'message': 'Merge pull request #1032 from ksuarz/master\n\nSERVER-20786 override singleThreaded'
            }

        :param project_name: The project ID in Evergreen
        :param max_results: (optional) Return no more than `max_results` results
        :return: A list containing build information on the most recent commits
        :rtype: list[dict]
        """
        response = helpers.get_as_json('{0}/rest/v1/projects/{1}/versions'.format(self.base_url, project_name))
        return response['versions'][:max_results]

    def get_build_variants_from_git_commit(self, project, commit_sha):
        """Get the build variants associated with the given project and Git commit SHA1.

        :param project: The Evergreen project ID
        :param commit_sha: The SHA1 of the desired Git commit
        :return: A list of build variant IDs
        :rtype: list[str]
        """
        response = helpers.get_as_json('{0}/rest/v1/projects/{1}/revisions/{2}'.format(self.base_url,
                                                                                       project,
                                                                                       commit_sha))
        return response['builds']

    def get_build_variants_from_revision_id(self, revision_id):
        """Get the build variants associated with with this project revision.

        This returns a list of build variant IDs from Evergreen. With this ID, you can find the specific tasks
        associated with that particular variant.

        :param revision_id: The revision ID in Evergreen
        :return: A list of build variant IDs
        :rtype: list[str]
        """
        response = helpers.get_as_json('{0}/rest/v1/versions/{1}'.format(self.base_url, revision_id))
        return response['builds']

    def get_build_variant_names_from_git_commit(self, project, commit):
        """Get the build variant names associated with this project and Git revision.

        This returns a list of variant names in human-readable format. Underscores received from the server are
        automatically replaced with hyphens, to aid in querying for other Evergreen information.

        :param project: The Evergreen project ID
        :param commit: The SHA1 of the desired Git commit
        :return: A list of build variant names
        :rtype: list[str]
        """
        response = helpers.get_as_json('{0}/rest/v1/projects/{1}/revisions/{2}'.format(self.base_url, project, commit))
        return [variant.replace('_', '-') for variant in response['build_variants']]

    def get_build_variant_names_from_revision_id(self, revision_id):
        """Get the build variant names associated with this project version.

        This returns a list of variant names in human-readable format. Underscores received from the server are
        automatically replaced with hyphens, to aid in querying for other Evergreen information.

        :param str revision_id: The version ID in Evergreen
        :return: A list of build variant names
        :rtype: list[str]
        """
        response = helpers.get_as_json('{0}/rest/v1/versions/{1}'.format(self.base_url, revision_id))
        return [variant.replace('_', '-') for variant in response['build_variants']]

    def get_tasks_from_build_variant(self, build_variant_id):
        """Get the tasks associated with this build ID.

        This returns a JSON-compatible dict describing the status of the tasks. The keynames are the names of each task;
        the values are subdocuments with more information. For example, to extract all of the task names:

            >>> evg = EvergreenClient()
            >>> tasks = evg.get_tasks_from_build_variant('performance_linux_mmap_standalone_9664b4bd7d19144b801767ff8b014520b24a56bc_15_10_21_20_49_17')
            >>> sorted(tasks.keys())
            [u'geo', u'insert', u'misc', u'query', u'singleThreaded', u'update', u'where']
            >>> tasks['geo']['task_id']
            u'performance_linux_mmap_standalone_geo_9664b4bd7d19144b801767ff8b014520b24a56bc_15_10_21_20_49_17'

        :param build_variant_id: The build ID of a build variant in Evergreen
        :return: A JSON-compatible dictionary of task information
        :rtype: dict[str, dict]
        """
        response = helpers.get_as_json('{0}/rest/v1/builds/{1}'.format(self.base_url, build_variant_id))
        return response['tasks']

    def get_test_names_from_task(self, task_id):
        """Get the tests associated with this task ID.

        Only the test names are returned; other information is stripped away.

        :param task_id: The task ID of a task in Evergreen
        :return: A list of test names
        :rtype: list
        """
        response = helpers.get_as_json('{0}/rest/v1/tasks/{1}'.format(self.base_url, task_id))
        return response['test_results'].keys()

    def get_failed_tests(self, task_id):
        """Get the tests that have failed for this task.

        :param task_id:
        :return:
        """
        response = helpers.get_as_json('{0}/rest/v1/tasks/{1}'.format(self.base_url, task_id))
        if response['aborted']:
            self.logger.warning('Searching for failed tests in a task that has been aborted')

        failed_tests = []
        for test, result in response['test_results'].iteritems():
            if result['status'] != 'pass':
                failed_tests.append(test)
        return failed_tests
