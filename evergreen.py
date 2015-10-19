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

import json
import re
import requests


DEFAULT_EVERGREEN_ENDPOINT = 'https://evergreen.mongodb.com/rest/v1'
"""The default Evergreen endpoint."""


class EvergreenClient(object):
    """Allows for interaction with an Evergreen server."""
    def __init__(self, endpoint_url=None):
        """Create a new handle to an Evergreen server.

        :param endpoint_url: (optional) The URL to the Evergreen endpoint. If not specified, uses a reasonable default.
        """
        if endpoint_url:
            self.endpoint = endpoint_url
        else:
            self.endpoint = DEFAULT_EVERGREEN_ENDPOINT

    def get_recent_versions(self, project_name, max_results=10):
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
        response = requests.get('{0}/projects/{1}/versions'.format(self.endpoint, project_name))
        if not response.ok:
            response.raise_for_status()
        else:
            return response.json()['versions'][:max_results]

    def get_variants_from_revision(self, project, revision):
        """Get the build variants associated with the given project and Git revision.

        :param project: The Evergreen project ID
        :param revision: The SHA1 of the desired Git commit
        :return: A list of build variant IDs
        :rtype: list[str]
        """
        response = requests.get('{0}/projects/{1}/revisions/{2}'.format(self.endpoint, project, revision))
        if not response.ok:
            response.raise_for_status()
        else:
            return response.json()['builds']

    def get_variants_from_version(self, version_id):
        """Get the build variants associated with with this project version.

        This returns a list of build variant IDs from Evergreen. With this ID, you can find the specific tasks
        associated with that particular variant.

        :param version_id: The version ID in Evergreen
        :return: A list of build variant IDs
        :rtype: list[str]
        """
        response = requests.get('{0}/versions/{1}'.format(self.endpoint, version_id))
        if not response.ok:
            response.raise_for_status()
        else:
            return response.json()['builds']

    def get_variant_names_from_revision(self, project, revision):
        """Get the variant names associated with this project and Git revision.

        This returns a list of variant names in human-readable format. Hyphens received from the server are
        automatically replaced with underscores, to aid in querying for other Evergreen information.

        :param project: The Evergreen project ID
        :param revision: The SHA1 of the desired Git commit
        :return: A list of build variant names
        :rtype: list[str]
        """
        response = requests.get('{0}/projects/{1}/revisions/{2}'.format(self.endpoint, project, revision))
        if not response.ok:
            response.raise_for_status()
        else:
            return [variant.replace('-', '_') for variant in response.json()['build_variants']]

    def get_variant_names_from_version(self, version_id):
        """Get the variant names associated with this project version.

        This returns a list of variant names in human-readable format. Hyphens received from the server are
        automatically replaced with underscores, to aid in querying for other Evergreen information.

        :param version_id: The version ID in Evergreen
        :return: A list of build variant names
        :rtype: list[str]
        """
        response = requests.get('{0}/versions/{1}'.format(self.endpoint, version_id))
        if not response.ok:
            response.raise_for_status()
        else:
            return [variant.replace('-', '_') for variant in response.json()['build_variants']]

    def get_tasks_from_variant(self, build_id):
        """Get the tasks associated with this build ID.

        This returns a JSON-compatible dict describing the status of the tasks. The keynames are the names of each task;
        the values are subdocuments with more information. For example, to extract all of the task names:

            >>> evg = EvergreenClient()
            >>> tasks = evg.get_tasks_from_variant('performance_linux_mmap_standalone_9664b4bd7d19144b801767ff8b014520b24a56bc_15_10_21_20_49_17')
            >>> tasks.keys()
            ['geo', 'insert', 'misc', 'query', 'singleThreaded', 'update', 'where']
            >>> tasks['geo']['task_id']
            'performance_linux_mmap_standalone_geo_9664b4bd7d19144b801767ff8b014520b24a56bc_15_10_21_20_49_17'

        :param build_id: The build ID of a build variant in Evergreen
        :return: A JSON-compatible dictionary of task information
        :rtype: dict
        """
        response = requests.get('{0}/builds/{1}'.format(self.endpoint, build_id))
        if not response.ok:
            response.raise_for_status()
        else:
            return response.json()['tasks']

    def get_testnames_from_task(self, task_id):
        """Get the tests associated with this task ID.

        Only the test names are returned; other information is stripped away.

        :param task_id: The task ID of a task in Evergreen
        :return: A list of test names
        :rtype: list
        """
        response = requests.get('{0}/tasks/{1}'.format(self.endpoint, task_id))
        if not response.ok:
            response.raise_for_status()
        else:
            return response.json()['test_results'].keys()


class Project(object):
    """Represents a project in Evergreen."""

    def __init__(self, initializer):
        """Initialize a new project.

        Create a new configuration, in JSON format, that represents the configuration of the project in Evergreen.
        The initializer can be one of several types:

            - str: Treated as a file path to a file to open
            - file: File descriptor from which to open the file. Must be readable
            - dict: A JSON-compatible dict used directly as the configuration

        :param initializer: A file, filename, or JSON-compatible dictionary from which to create the configuration
        """
        if isinstance(initializer, str):
            with open(initializer, 'r') as fd:
                self.config = json.load(fd)
        elif isinstance(initializer, file):
            self.config = json.load(initializer)
        elif isinstance(initializer, dict):
            self.config = initializer
        else:
            raise TypeError('Initializer is not a valid type')

    def get_name(self):
        """Get the Evergreen project ID name for this project.

        :return: The ID in Evergreen for this project
        :rtype: str
        """
        return self.config['name']

    def get_variants(self, filter=None):
        """Get the variants used in this project.

        If `filter` is None, this retrieves all variants in this project. Otherwise, `filter` is treated as a regular
        expression and it returns all variants that match the pattern.

        :param filter: (optional) Select only variants matching the filter
        :return: The variants for this Evergreen project.
        :rtype: list[str]
        """
        result = []
        for variant in self.config['variants']:
            if filter is None or re.match(filter, variant['name']):
                result.append(variant['name'])
        return result

    def get_tasks(self, variant, filter=None):
        """Get the tasks for this variant.

        If no variant with this name exists, an empty list is returned.

        :param variant: The name of the variant
        :return: The tasks associated with this variant
        :rtype: list[str]
        """
        result = []
        for v in self.config['variants']:
            if v['name'] != variant:
                continue

            for task in v['tasks']:
                result.append(task['name'])

        return result

    def get_tests(self, variant, task, filter=None):
        """Get the tests associated with the given variant and task.

        :param variant:
        :param task:
        :param filter: (optional)
        :return: A list of test names
        :rtype: list[str]
        """
        pass

    def save_to_file(self, destination):
        """Save this configuration to a new file.

        :param destination: A filename or file object to save to. Must be writable
        :return: None
        """
        if isinstance(destination, str):
            fd = open(destination, 'w')
        elif isinstance(destination, file):
            fd = destination
        else:
            raise TypeError('destination must be a file or file name')

        json.dump(self.config, fd)
        fd.close()

    @staticmethod
    def new_from_evergreen(evg_client, project_name):
        """Look up a project's configuration directly from Evergreen.

        :param evg_client: An EvergreenClient
        :param project_name: The identifier of the project in Evergreen
        :return: A new Project object.
        """
        # TODO
        return None
