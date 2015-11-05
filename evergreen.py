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

from __future__ import print_function
import logging

import helpers


DEFAULT_EVERGREEN_URL = 'https://evergreen.mongodb.com'
"""The default Evergreen URL."""


class EvergreenError(Exception):
    """Generic class for Evergreen errors."""
    pass


class Empty(EvergreenError):
    """Indicates that an empty response from Evergreen was not expected."""
    pass


class Client(object):
    """Allows for interaction with an Evergreen server.

    This class has two sets of methods. The first type are the "query" functions, which are simple wrappers around the
    Evergreen JSON endpoints. They handle making the request and return the output unchanged as a JSON-compatible
    dictionary.

    The second group builds on the query functions, and they return useful information about Evergreen revisions, build
    variants and tasks by extracting the relevant information. Most of these are implemented as generators to cache
    the results of the HTTP queries.
    """

    def __init__(self, configuration=None, verbose=True):
        """Create a new handle to an Evergreen server.

        :param str|file configuration: (optional) A personal YAML configuration for Evergreen
        :param bool verbose: (optional) Control the verbosity of logging statements
        """
        self.logger = logging.getLogger('evergreen')
        self.logger.level = logging.INFO if verbose else logging.WARNING

        # Parse the config file
        try:
            yml = helpers.file_as_yaml(configuration)
            self.headers = {
                'auth-username': yml['user'],
                'api-key': yml['api_key']
            }
            self.base_url = yml['ui_server_host']
        except (TypeError, KeyError):
            self.base_url = DEFAULT_EVERGREEN_URL
            self.headers = {}

    def query_project_history(self, project):
        """Gets all the information on the most recent revisions.

        Evergreen endpoint: /rest/v1/projects/{project_name}/versions

        :param str project: The name of the Evergreen project (e.g. 'performance', 'sys-perf')
        :rtype: dict
        """
        return helpers.get_as_json(
            '{url}/rest/v1/projects/{project_id}/versions'.format(url=self.base_url, project_id=project),
            headers=self.headers
        )

    def query_revision_by_commit(self, project, revision):
        """Get Evergreen run information on a given Git commit.

        Evergreen endpoint: /rest/v1/projects/{project_id}/revisions/{revision}

        :param str project:  The name of the Evergreen project (e.g. 'performance', 'sys-perf')
        :param str revision: The SHA1 of the desired Git commit
        :rtype: dict
        """
        return helpers.get_as_json(
            '{url}/rest/v1/projects/{project_id}/revisions/{revision}'.format(url=self.base_url,
                                                                              project_id=project,
                                                                              revision=revision),
            headers=self.headers
        )

    def query_revision(self, revision_id):
        """Get information on a given revision.

        Evergreen endpoint: /rest/v1/versions/{revision_id}

        :param str revision_id: The Evergreen ID of a particular revision or version
        :rtype: dict
        """
        return helpers.get_as_json(
            '{url}/rest/v1/versions/{version_id}'.format(url=self.base_url, version_id=revision_id),
            headers=self.headers
        )

    def query_revision_status(self, revision_id):
        """Get the status of a particular revision.

        Evergreen endpoint: /rest/v1/versions/{revision_id}/status

        :param str revision_id: The Evergreen ID of a particular revision or version
        :rtype: dict
        """
        return helpers.get_as_json(
            '{url}/rest/v1/versions/{version_id}/status'.format(url=self.base_url, version_id=revision_id),
            headers=self.headers
        )

    def query_build_variant(self, build_variant_id):
        """Get information on a particular build variant.

        Evergreen endpoint: /rest/v1/builds/{build_id}

        :param str build_variant_id: The Evergreen ID of a particular build variant
        :rtype: dict
        """
        return helpers.get_as_json(
            '{url}/rest/v1/builds/{build_id}'.format(url=self.base_url, build_id=build_variant_id),
            headers=self.headers
        )

    def query_build_variant_status(self, build_variant_id):
        """Get the status of a particular build variant.

        Evergreen endpoint: /rest/v1/builds/{build_id}/status

        :param str build_variant_id: The Evergreen ID of a particular build variant
        :rtype: dict
        """
        return helpers.get_as_json(
            '{url}/rest/v1/builds/{build_id}/status'.format(url=self.base_url, build_id=build_variant_id),
            headers=self.headers
        )

    def query_task(self, task_id):
        """Get information on a particular task.

        Evergreen endpoint: /rest/v1/tasks/{task_id}

        :param str task_id: The Evergreen ID of a particular task
        :rtype: dict
        """
        return helpers.get_as_json(
            '{url}/rest/v1/tasks/{task_id}'.format(url=self.base_url, task_id=task_id),
            headers=self.headers
        )

    def query_task_status(self, task_id):
        """Get the status of a particular task

        Evergreen endpoint: /rest/v1/tasks/{task_id}/status

        :param str task_id: The Evergreen ID of a particular task
        :rtype: dict
        """
        return helpers.get_as_json(
            '{url}/rest/v1/tasks/{task_id}/status'.format(url=self.base_url, task_id=task_id),
            headers=self.headers
        )

    def query_task_history(self, task_name):
        """Get the history of a particular task.

        Evergreen endpoint: /rest/v1/tasks/{task_name}/history

        :param str task_name: The Evergreen ID of a particular task
        :rtype: dict
        """
        return helpers.get_as_json(
            '{url}/rest/v1/tasks/{task_name}/history'.format(url=self.base_url, task_name=task_name)
        )

    def get_recent_revisions(self, project_name, max_results=10):
        """Get the most recent revisions for an Evergreen project.

        Valid project names include "performance" for the MongoDB Perf Project, "sys-perf" for System Performance, and
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
        return self.query_project_history(project_name)['versions'][:max_results]

    def query_task_perf_tags(self, task_name, task_id):
        """Get the tag data of a particular task in the Performance project.

        This works for the performance project. The sys-perf and longevity projects may return empty responses; use
        a different method instead.

        Evergreen endpoint: /api/2/task/{task_id}/json/tags/{task_name}/perf

        :param str task_name: The common name of the task
        :param str task_id: The Evergreen ID of a particular task
        :rtype: list
        """
        return helpers.get_as_json(
            '{url}/api/2/task/{task_id}/json/tags/{task_name}/perf'.format(url=self.base_url,
                                                                           task_id=task_id,
                                                                           task_name=task_name),
            headers=self.headers
        )

    def build_variants_from_git_commit(self, project, commit_sha):
        """Generates the names and Evergreen IDs of build variants.

        Build variant names have underscores replaced with hyphens, to aid in

        :param str project: The name of the Evergreen project
        :param str commit_sha: The SHA1 of the Git commit
        :return: Tuples in the form ("build-variant-name", "build-variant-id")
        :rtype: tuple(str, str)
        """
        response = helpers.get_as_json('{0}/rest/v1/projects/{1}/revisions/{2}'.format(self.base_url,
                                                                                       project,
                                                                                       commit_sha),
                                       headers=self.headers)
        names = sorted([x.replace('_', '-') for x in response['build_variants']])
        ids = sorted(response['builds'])

        if not names or not ids:
            raise Empty('No builds found at commit {commit} in project {project}'.format(commit=commit_sha,
                                                                                         project=project))

        for item in zip(names, ids):
            yield item

    def build_variants_from_revision_id(self, revision_id):
        """Generates the names and Evergreen IDs of build variants.

        :param str revision_id: The ID of the revision in Evergreen
        :return: Tuples in the form ("build-variant-name", "build-variant-id")
        :rtype: tuple(str, str)
        """
        response = helpers.get_as_json('{0}/rest/v1/versions/{1}'.format(self.base_url, revision_id),
                                       headers=self.headers)
        names = sorted([x.replace('_', '-') for x in response['build_variants']])
        ids = sorted(response['builds'])

        if not names or not ids:
            raise Empty('No builds found for Evergreen revision {rev}'.format(revision_id))

        for item in zip(names, ids):
            yield item

    def tasks_from_build_variant(self, build_variant_id):
        """Generates the names and Evergreen IDs of the tasks associated with this build variant.

        :param str build_variant_id: The ID of the build variant in Evergreen
        :return: Tuples in the form ("task-name", "task-id")
        :rtype: tuple(str, str)
        """
        build_info = self.query_build_variant(build_variant_id)
        tasks = build_info['tasks']

        if not tasks:
            raise Empty('No tasks found for build variant {variant}'.format(variant=build_variant_id))

        for task_name in tasks.keys():
            yield (task_name, tasks[task_name]['task_id'])

    def tests_from_task(self, task_id):
        """Generates the names and status information of the tests associated with this task.

        The test status information looks something like this:
        {
            'logs': {'url': '...'},
            'status': 'pass',
            'time_taken': 123123123
        }

        :param str task_id: The ID of the task in Evergreen
        :rtype: tuple(str, dict)
        """
        task_info = self.query_task(task_id)

        if not task_info['test_results']:
            raise Empty('No test results found for task {task}'.format(task=task_id))

        for test_name in task_info['test_results'].keys():
            yield (test_name, task_info['test_results'][test_name])

    def failed_tests_from_task(self, task_id):
        """Generates the tests that have failed for this task.

        :param str task_id: The ID of the task in Evergreen
        :rtype: str
        """
        response = self.query_task(task_id)
        if response['aborted']:
            self.logger.warning('Searching for failed tests in a task that has been aborted')

        if not response['test_results']:
            raise Empty('No test results found for task {task}'.format(task=task_id))

        for test, result in response['test_results'].iteritems():
            if result['status'] != 'pass':
                yield test
