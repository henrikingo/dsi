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
import doctest
import itertools
import json

# os.path is used for pydoc. It won't need to be commented out when we move that test into a
#  proper test function.
import os.path # pylint: disable=unused-import

# TODO: It would be nice if the override class handled adding new overrides transparently

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

    The analysis scripts traverse this hierarchy, selecting the appropriate build variant, rule and
    test name. If an override exists, it uses that data as the reference point against which to find
    regressions, rather than the usual data.
    """
    def __init__(self, initializer):
        """Create a new override.

        :param initializer: The starting point for building overrides
        """
        if initializer is None:
            self.overrides = {}
        elif isinstance(initializer, str):
            with open(initializer) as file_:
                self.overrides = json.load(file_)
        elif isinstance(initializer, dict):
            self.overrides = initializer
        else:
            raise TypeError('initializer must be a file, filename or dictionary')

    def update_test(self, build_variant, test, rule, new_data, ticket): # pylint: disable=too-many-arguments
        """Update the override reference data for the given test.

        :param str build_variant: The Evergreen name of the build variant
        :param str test: The Evergreen name of the test within that build variant
        :param str rule: The regression analysis rule (e.g. "reference", "ndays")
        :param dict new_data: The raw data for this test to use as a new reference point
        :param str ticket: The JIRA ticket to attach to this override reference point
        :return: The old value of the data for this particular build variant,
                test and rule, if one existed
        :rtype: dict
        """
        # Find the overrides for this build variant...
        try:
            variant_ovr = self.overrides[build_variant]
        except KeyError:
            self.overrides[build_variant] = {
                'reference': {},
                'ndays': {},
                'threshold': {}
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
            rule_ovr[test]['ticket'] = previous_data['ticket']
            rule_ovr[test]['ticket'].append(ticket)
        except AttributeError:
            # There's something else there but it's not a list, so convert it to one
            rule_ovr[test]['ticket'] = [previous_data['ticket'], ticket]
        except KeyError:
            # There is no previous ticket associated with this override
            rule_ovr[test]['ticket'] = [ticket]

        return previous_data

    def get_tickets(self, rule='reference'):
        """ Return a list of all tickets mentioned in overrides

        :param str rule: Which rule to check for tickets. (Default reference)
        :return: A set of strings of the tickets referenced in the overrides

        >>> Override(None).get_tickets()
        set([])
        >>> over = Override(os.path.join(os.path.dirname(__file__),\
                                         "../testcases/perf_override.json"))
        >>> over.get_tickets()
        set([u'BF-1262', u'BF-1449', u'BF-1461', u'SERVER-19901', u'SERVER-20623', u'SERVER-21263',\
 u'BF-1169', u'SERVER-20018', u'mmapspedup', u'geo', u'SERVER-21080'])
        >>> over.get_tickets('threshold')
        set([u'PERF-443'])
        """

        tickets = set()
        for variant_value in self.overrides.values():
            if rule in variant_value:
                ref = variant_value[rule]
                tickets = tickets.union(set(itertools.chain(*[test['ticket'] for test in
                                                              ref.values() if 'ticket' in
                                                              test.keys() and isinstance(
                                                                  test['ticket'], list)])))
        return tickets

    def get_overrides_by_ticket(self, ticket):
        """Get the overrides created by a given ticket.

        :param str ticket: The ID of a JIRA ticket (e.g. PERF-226)
        :rtype: list[dict]
        """

        raise NotImplementedError()

    def delete_overrides_by_ticket(self, ticket, rule='reference'):
        """Remove the overrides created by a given ticket.

        The override is completely removed if the ticket is the only
        one in the list. If there are other tickets in the list, the
        ticket is just removed from the list

        :param str ticket: The ID of a JIRA ticket (e.g. SERVER-20123)
        :param str rule: Which rule to delete from. (Default reference)

        In the example below, the first override should be removed
        because SERVER-21080 is the only ticket in the list, even if
        it shows up twice. The second test has two distinct tickets,
        so when we delete SERVER-21080 it is just removed from the
        list.
        >>> over =  Override({"linux-mmap-repl":{\
        "reference":{\
            "Commands.CountsIntIDRange":{\
                "ticket":[\
                    "SERVER-21080",\
                    "SERVER-21080"\
                ]\
            },\
            "Commands.CountsIntIDRange":{\
                "ticket":[\
                    "SERVER-21080",\
                    "SERVER-21081"\
                ]\
            }}}})
        >>> over.delete_overrides_by_ticket("SERVER-21080", "reference")
        Deleting test Commands.CountsIntIDRange from variant linux-mmap-repl and rule reference,\
 but override remains
        Remaining tickets are ['SERVER-21081']
        >>> over.overrides
        {'linux-mmap-repl': {'reference': {'Commands.CountsIntIDRange': {'ticket':\
 ['SERVER-21081']}}}}

        """
        for build_variant in self.overrides:
            if rule in self.overrides[build_variant]:
                # Remove anything that can be blanket removed. Can't otherwise remove from something
                # we're iterating over
                self.overrides[build_variant][rule] = {name: test for (name, test) in
                                                       self.overrides[build_variant][rule].items()
                                                       if 'ticket' in test and
                                                       test['ticket'].count(ticket) !=
                                                       len(test['ticket'])}
                for test in self.overrides[build_variant][rule]:
                    #Look to see if it should be pulled from the ticket list
                    if 'ticket' in self.overrides[build_variant][rule][test]:
                        if ticket in self.overrides[build_variant][rule][test]['ticket']:
                            self.overrides[build_variant][rule][test]['ticket'].remove(ticket)
                            print("Deleting test {} from variant {} and rule {}, but "
                                  "override remains".format(test, build_variant, rule))
                            print("Remaining tickets are {}".format(str(
                                self.overrides[build_variant][rule][test]['ticket'])))

    def save_to_file(self, file_or_filename):
        """Saves this override to a JSON file.

        :param file|str file_or_filename: A file or filename destination to save to
        """
        if isinstance(file_or_filename, str):
            with open(file_or_filename, 'w') as file_ptr:
                json.dump(
                    self.overrides, file_ptr, file_or_filename, indent=4,
                    separators=[',', ':'], sort_keys=True)
        elif isinstance(file_or_filename, file):
            json.dump(
                self.overrides, file_or_filename, indent=4, separators=[',', ':'], sort_keys=True)
        else:
            raise TypeError('Argument must be a file or filename')

if __name__ == "__main__":
    doctest.testmod()
