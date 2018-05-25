#!/usr/bin/env python2.7
"""
Fetch, analyze and visualize results from builds created with multi_patch_builds.py.

Note, while this takes as input the serialized file (with --continue), it will not
write back to that file. This script only prints out a csv file (or optionally writes to file).
"""

from __future__ import print_function

import os
import sys
import yaml

from evergreen import evergreen_client


class OptionError(Exception):
    """Exception raised for erroneous command line options."""
    pass


class FindByTag(object):
    """
    Find Evergreen patch build by tag.
    """

    def __init__(self, project, tag):
        """Constructor."""
        self.project = project
        self.tag = tag
        self._evergreen_client = None

    @property
    def evergreen_client(self):
        """
        Get evergreen_client lazily.
        """
        if self._evergreen_client is None:
            path = os.path.expanduser('~/.evergreen.yml')
            with open(path) as config_file:
                self._evergreen_client = evergreen_client.Client(yaml.load(config_file))
        return self._evergreen_client

    def find_version(self):
        """
        Return a URL to the build that is tagged with self.tag.
        """
        return self.evergreen_client.find_perf_tag(self.project, self.tag)


def main(cli_args=None):
    """Main function"""
    if cli_args is None:
        cli_args = sys.argv[1:]

    if len(cli_args) < 1 or len(cli_args) > 2 or not isinstance(cli_args[0], basestring) or \
       not isinstance(cli_args[1], basestring):
        print("find_tag.py - Find sys-perf patch build by tag")
        print("Usage: find_tag.py PROJECT TAG")
        sys.exit(1)

    find_by_tag = FindByTag(cli_args[0], cli_args[1])
    url = find_by_tag.evergreen_client.base_url
    version_id = find_by_tag.find_version()
    print("{}/version/{}".format(url, version_id))


if __name__ == '__main__':
    main()
