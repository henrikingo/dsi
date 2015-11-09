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


# TODO: It would be nice if the override class handled adding new overrides transparently


class NotYetImplemented(RuntimeError):
    """Indicates that this function has yet to be implemented."""
    pass


class Override(object):
    """Represents an override for a performance test.

    The override data is structured in a hierarchy:

        {
            "build_variant": {
                "rule": {
                    "test_name": {
                        <data>
                    },
                    ...
                },
                ...
            },
            ...
        }

    The analysis scripts traverse this hierarchy, selecting the appropriate build variant, rule and test name. If an
    override exists, it uses that data as the reference point against which to find regressions, rather than the usual
    data.
    """
    def __init__(self, initializer):
        """Create a new override.

        :param initializer: The starting point for building overrides
        """
        if initializer is None:
            self.overrides = {}
        elif isinstance(initializer, str):
            with open(initializer) as fd:
                self.overrides = json.load(fd)
        elif isinstance(initializer, dict):
            self.overrides = initializer
        else:
            raise TypeError('initializer must be a file, filename or dictionary')

    def update_test(self, build_variant, test, rule, new_data, ticket):
        """Update the override reference data for the given test.

        :param str build_variant: The Evergreen name of the build variant
        :param str test: The Evergreen name of the test within that build variant
        :param str rule: The regression analysis rule (e.g. "reference", "ndays")
        :param dict new_data: The raw data for this test to use as a new reference point
        :param str ticket: The JIRA ticket to attach to this override reference point
        :return: The old value of the data for this particular build variant, test and rule, if one existed
        :rtype: dict
        """
        # Find the overrides for this build variant...
        try:
            variant_ovr = self.overrides[build_variant]
        except KeyError:
            self.overrides[build_variant] = {
                'reference': {},
                'ndays': {}
            }
            variant_ovr = self.overrides[build_variant]

        # ...then, for this regression rule (e.g. 'reference', 'ndays')...
        try:
            rule_ovr = variant_ovr[rule]
        except KeyError:
            variant_ovr[rule] = {}
            rule_ovr = variant_ovr[rule]

        # ...and lastly, the raw data for the test
        try:
            previous_data = rule_ovr[test]
        except KeyError:
            previous_data = {}
        finally:
            rule_ovr[test] = new_data

        # Attach a ticket number
        try:
            rule_ovr[test]['ticket'].append(ticket)
        except AttributeError:
            # There's something else there but it's not a list, so convert it to one
            rule_ovr[test]['ticket'] = [rule_ovr[test]['ticket'], ticket]
        except KeyError:
            # There is no previous ticket associated with this override
            rule_ovr[test]['ticket'] = [ticket]

        return previous_data

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
        for build_variant in self.overrides:
            for rule in self.overrides[build_variant]:
                for test in self.overrides[build_variant][rule]:
                    try:
                        if self.overrides[build_variant][rule][test]['ticket'].contains(ticket):
                            del self.overrides[build_variant][rule][test]
                    except KeyError:
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
