"""Module to track state dependencies during override file update operations.
"""

from __future__ import print_function
import copy
import itertools
import json
import logging
import re
import sys

import requests

from evergreen import evergreen_client
from evergreen import helpers
from evergreen.history import History

LOGGER = None
WARNER = None


def _setup_logging(verbose):
    """Initialize the logger and warner
    :param bool verbose: specifies the level at which LOGGER logs.
    """
    global LOGGER, WARNER  # pylint: disable=global-statement
    WARNER = logging.getLogger('override.update.warnings')
    LOGGER = logging.getLogger('override.update.information')

    if verbose:
        LOGGER.setLevel(logging.DEBUG)
    else:
        LOGGER.setLevel(logging.INFO)


class OverrideError(Exception):
    """Generic class for Override errors."""
    pass


class TestDataNotFound(OverrideError):
    """Indicates that test data for a desired override update could not be found in the latest
    project revisions.
    """
    pass


class Override(object):  # pylint: disable=too-many-instance-attributes
    """This class handles operations related to updating an override file.
    """

    def __init__(  # pylint: disable=too-many-arguments
            self,
            project,
            override_info=None,
            config_file=None,
            reference=None,
            variants=None,
            tasks=None,
            tests=None,
            verbose=False):
        """
        :param str project: The project name in Evergreen
        :param str|dict override_info: The filename or dict representing the override file JSON
        :param str config_file: For automated tests, a config with Evergreen & Github creds
        :param str reference: A Git SHA1 prefix (min. 7 char) or tag to use as a reference
        :param list[str] variants: The build variant(s) to override
        :param list[str] tasks: The task(s) to override
        :param list[str] tests: The test(s) to override
        :param bool verbose: The setting for our logger (verbose corresponding to DEBUG mode)
        """
        _setup_logging(verbose)

        self.project = project

        if not override_info:
            self.overrides = {}
        elif isinstance(override_info, str):
            with open(override_info) as file_handle:
                self.overrides = json.load(file_handle)
        elif isinstance(override_info, dict):
            self.overrides = override_info
        else:
            raise TypeError('override_info must be a file, filename, or dictionary')

        if config_file:
            creds = helpers.file_as_yaml(config_file)
            self.evg = evergreen_client.Client(creds['evergreen'])
        else:
            self.evg = None

        if reference:
            if creds is None:
                creds = helpers.create_credentials_config()
                self.evg = evergreen_client.Client(creds['evergreen'])
            # Are we comparing against a tag or a commit?
            try:
                # Attempt to query Evergreen by treating this reference as a Git commit
                full_reference = helpers.get_full_git_commit_hash(reference,
                                                                  creds['github']['token'])
                self.commit = full_reference
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
                LOGGER.debug(
                    'Treating reference point "{tag}" as a tagged baseline'.format(tag=self.commit))
                LOGGER.debug('Getting {proj} project information from commit {commit}'.format(
                    proj=self.project, commit=self.commit))
        else:
            self.commit = None

        # variants, tasks, and tests default to None. Unless we are explicitly doing a "general"
        # overrides file update (i.e. the specified tasks & tests are updated for all variants),
        # we don't need the Override object to require this information upon initialization.
        self.variants = variants
        self.tasks = tasks
        self.tests = tests

        # used for logging information after an update has been made.
        self.build_variants_applied = set()
        self.tasks_applied = set()
        self.tests_applied = set()
        self.summary = {}
        self.delete_summary = {}

    def _log_final_checks(self):
        """Sanity checks, called at the very end of general override rule updates (excludes the
        delete ticket & update operation)
        """
        for unused_test in [test for test in self.tests if test not in self.tests_applied]:
            WARNER.warn('Pattern not applied for tests: {0}'.format(unused_test))

        for unused_task in [task for task in self.tasks if task not in self.tasks_applied]:
            WARNER.warn('Pattern not applied for tasks: {0}'.format(unused_task))

        for unused_variant in [
                variant for variant in self.variants if variant not in self.build_variants_applied
        ]:
            WARNER.warn('Pattern not applied for build variants: {0}'.format(unused_variant))
        self._log_summary()

    def _log_summary(self):  # pylint: disable=too-many-branches
        """Review and print a summary of what's been accomplished to the logfile.
        All operations that involve updating the override file will use this function.
        """
        has_updated = False
        has_deleted = False
        for rule in self.summary:
            for variant in self.summary[rule]:
                for task in self.summary[rule][variant]:
                    task_updates = self.summary[rule][variant][task]
                    if isinstance(task_updates, list) and len(task_updates) > 0:
                        has_updated = True

        for variant in self.delete_summary.keys():
            if self.delete_summary[variant] == {}:
                del self.delete_summary[variant]
                continue
            for task in self.delete_summary[variant]:
                if self.delete_summary[variant][task]:
                    has_deleted = True

        if not has_updated and not has_deleted:
            WARNER.critical('No overrides have changed.')
        else:
            LOGGER.info('The following tests were deleted:')
            LOGGER.info(
                json.dumps(self.delete_summary, indent=2, separators=[',', ': '], sort_keys=True))
            for rule in self.summary:
                LOGGER.info('The following tests were overridden for rule {0}:'.format(rule))
                LOGGER.info(
                    json.dumps(
                        self.summary[rule], indent=2, separators=[',', ': '], sort_keys=True))
        LOGGER.debug('Override update complete.')

    def _get_task_history(self, task_name, task_id):
        """Helper function to get the performance data for a particular task.

        :type task_name: str
        :type task_id: str
        :rtype: History
        """
        if self.compare_to_commit:
            task_data = self.evg.query_mongo_perf_task_history(task_name, task_id)
        else:
            task_data = self.evg.query_mongo_perf_task_tags(task_name, task_id)

        # Examine the history data
        history = History(task_data)
        return history

    def _get_test_reference_data(self, history, test_name):
        """Helper function to get the data for a particular test from a specific commit or tag.

        :type history: History
        :type test_name: str
        :rtype: dict
        """
        if self.compare_to_commit:
            test_reference = history.series_at_revision(test_name, self.commit)
        else:
            test_reference = history.series_at_tag(test_name, self.commit)
        return test_reference

    def update_override(self, rule, new_override_val=None, ticket=None):
        """Update a performance override rule.

        :param str rule: The rule to override (reference, ndays, threshold)
        :param dict new_override_val: Required only when rule == 'threshold', where
               new_override_val has keys 'thread_threshold' and 'threshold' corresponding to float
               values.
        :param str ticket: Associate a JIRA ticket with this update.
        """
        self.summary[rule] = {}
        # Find the build variants for the project at this Git commit
        for build_variant_name, build_variant_id in self.evg.build_variants_from_git_commit(
                self.project, self.commit):
            match = helpers.matches_any(build_variant_name, self.variants)
            if not match:
                LOGGER.debug('Skipping build variant: {0}'.format(build_variant_name))
                continue

            self.build_variants_applied.add(match)
            self.summary[rule][build_variant_name] = {}
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
                self.summary[rule][build_variant_name][task_name] = []
                LOGGER.debug('\tProcessing task: {0}'.format(task_name))

                if rule is not 'threshold':
                    history = self._get_task_history(task_name, task_id)

                # Cycle through the names of the tests in this task
                try:
                    for test_name, _ in self.evg.tests_from_task(task_id):
                        match = helpers.matches_any(test_name, self.tests)
                        if not match:
                            LOGGER.debug('\t\tSkipping test: {0}'.format(test_name))
                            continue

                        LOGGER.debug('\t\tProcessing test: {0}'.format(test_name))

                        if rule is not 'threshold':
                            # Get the reference data we want to use as the override value
                            new_override_val = self._get_test_reference_data(history, test_name)
                            if not new_override_val:
                                LOGGER.warning(
                                    'No data for {bv}.{task}.{test} at reference {ref}'.format(
                                        bv=build_variant_name,
                                        task=task_name,
                                        test=test_name,
                                        ref=self.commit))
                                continue

                        self.tests_applied.add(match)
                        self.summary[rule][build_variant_name][task_name].append(test_name)

                        # Finally, update the old override rule
                        self.update_test(build_variant_name, task_name, test_name, rule,
                                         new_override_val, ticket)

                except evergreen_client.Empty as error:
                    # Typically happens if a task didn't run or had system failure
                    LOGGER.warning(error)

        self._log_final_checks()

    def update_override_threshold(self, threshold, thread_threshold, ticket=None):
        """Update a performance threshold level override. Wrapper function to update_override.

        :param float threshold: The new threshold to use
        :param float thread_threshold: The new thread threshold to use
        :param str ticket: Associate a JIRA ticket with this override
        """
        new_override = {'threshold': threshold, 'thread_threshold': thread_threshold}
        self.update_override('threshold', new_override_val=new_override, ticket=ticket)

    def update_override_reference(self, ticket=None):
        """Update a performance reference override. Wrapper function to update_override.

        :param str ticket: Associate a JIRA ticket with this override
        """
        self.update_override('reference', ticket=ticket)

    def update_override_ndays(self, ticket=None):
        """Update a performance ndays override. Wrapper function to update_override.

        :param str ticket: Associate a JIRA ticket with this override
        """
        self.update_override('ndays', ticket=ticket)

    def _process_revision(self, revision_builds, variant_tests, tasks):
        """How many tests (by build variant) does this revision have data for?

        :param dict revision_builds: builds associated with a revision
        :param dict variant_tests: each str variant (key) is associated with a list[str] of
           tests (value).
        :type tasks: str|list[str]
        :rtype: int
        """
        # pylint: disable=too-many-locals,too-many-nested-blocks
        num_tests_missing_data = 0
        variant_tests_remaining = copy.deepcopy(variant_tests)
        for variant in variant_tests.keys():
            variant_info = revision_builds[variant]
            for task_name, task_info in variant_info['tasks'].iteritems():
                if task_info['status'] != 'success':
                    continue
                if 'compile' in task_name:
                    continue
                match = helpers.matches_any(task_name, tasks)
                if not match:
                    continue
                try:
                    for test_name, _ in self.evg.tests_from_task(task_info['task_id']):
                        if test_name in variant_tests[variant]:
                            variant_tests_remaining[variant].remove(test_name)
                except evergreen_client.Empty:
                    LOGGER.warning("Caught evergreen_client.Empty exception in "
                                   "_processing_revision in call to tests_from_task for "
                                   "task_id {0}. ".format(task_info['task_id']) +
                                   "Supressing error. This indicates something is wrong, "
                                   "but the current operation can still complete correctly.")

            tests_remain = variant_tests_remaining[variant]
            num_tests_missing_data += len(tests_remain)
            for test in tests_remain:
                LOGGER.debug('\tNo result for test {} in variant {}'.format(test, variant))
        return num_tests_missing_data

    def _get_recent_commit(self, overrides_to_update, tasks):
        """Helper function used during a delete and update operation. If no reference has been
        given, attempt to find a perf project revision that has the test data for all of the
        override rules that require updates.

        :type overrides_to_update: dict
        :type tasks: str|list[str]
        :raises: TestDataNotFound if no such reference is found within the 10 most recent revisions.
        """
        # get tests by variant (regardless of whether the rule is reference or ndays)
        # pylint: disable=too-many-locals
        if not self.evg:
            creds = helpers.create_credentials_config()
            self.evg = evergreen_client.Client(creds['evergreen'])
        variant_tests = {}
        # pylint: disable=unused-variable
        for rule_name, rule_variants in overrides_to_update.iteritems():
            for build_variant, test_list in rule_variants.iteritems():
                if build_variant not in variant_tests:
                    variant_tests[build_variant] = set()
                variant_tests[build_variant].update(test_list)
        # pylint: enable=unused-variable

        revision_case_count = []  # does the revision cover all variant-test cases?
        for revision_info in self.evg.get_recent_revisions(self.project):
            revision = revision_info['revision']
            # revision does not contain all the variants targeted in the update
            if set(variant_tests.keys()) > set(revision_info['builds'].keys()):
                continue
            LOGGER.debug('Processing revision: {0}'.format(revision))
            num_tests_missing_data = self._process_revision(revision_info['builds'], variant_tests,
                                                            tasks)
            revision_case_count.append((revision, num_tests_missing_data))
            if num_tests_missing_data == 0:
                self.commit = revision
                self.compare_to_commit = True
                LOGGER.info('Treating reference point "{commit}" as a Git commit'.format(
                    commit=self.commit))
                return
        # Could not find a revision with the necessary test data. Output an error message with some
        # details about the 'closest' most recent revision.
        (min_revision, min_count) = min(revision_case_count, key=lambda x: x[1])
        raise TestDataNotFound('Could not find test data for all the variant-task-test updates '
                               'needed within the 10 most recent revisions of project {}. '
                               'Revision {} comes closest with {} case(s) of missing test '
                               'data. Please re-run this operation with a commit reference '
                               'of your choice that will best address the necessary '
                               'updates.'.format(self.project, min_revision, min_count))

    def _update_multiple_overrides(self, overrides_to_update, tasks):
        """Called after a ticket deletion operation. In the event that tickets remain for an
        override case, we need to update the data associated with those tests. Because the rules
        and tests that require updates may not be the same across all variants, this function is
        used in place of the multiple calls to update_overrides we would have otherwise had to do.

        :param dict overrides_to_update: structured so that for every rule, we know the build
        variants and the corresponding list of tests that need to be updated
            i.e. {rule -> {build_variant -> {task -> [tests]}}}
        :param str|list[str] tasks: as of right now, the user must specify which tasks we should
        look at during the update operation. This will likely not be necessary after PERF-504 (adds
        task attribute to the override file) is implemented.
        """
        # pylint: disable=too-many-locals,too-many-nested-blocks
        if not self.commit:
            self._get_recent_commit(overrides_to_update, tasks)
        for rule, build_variant_tests in overrides_to_update.iteritems():
            LOGGER.debug('Updating overrides for rule {0}'.format(rule))
            self.summary[rule] = {}
            for build_variant_name, build_variant_id in self.evg.build_variants_from_git_commit(
                    self.project, self.commit):
                if build_variant_name not in build_variant_tests.keys():
                    LOGGER.debug('Skipping build variant: {0}'.format(build_variant_name))
                    continue
                self.summary[rule][build_variant_name] = {}
                LOGGER.debug('Processing build variant: {0}'.format(build_variant_name))

                tests = overrides_to_update[rule][build_variant_name]
                for task_name, task_id in self.evg.tasks_from_build_variant(build_variant_id):
                    if 'compile' in task_name:
                        LOGGER.debug('\tSkipping compilation stage')
                        continue
                    match = helpers.matches_any(task_name, tasks)
                    if not match:
                        LOGGER.debug('\tSkipping task: {0}'.format(task_name))
                        continue
                    self.summary[rule][build_variant_name][task_name] = []
                    LOGGER.debug('\tProcessing task: {0}'.format(task_name))

                    history = self._get_task_history(task_name, task_id)
                    try:
                        for test_name, _ in self.evg.tests_from_task(task_id):
                            if test_name not in tests:
                                LOGGER.debug('\t\tSkipping test: {0}'.format(test_name))
                                continue

                            self.summary[rule][build_variant_name][task_name].append(test_name)
                            LOGGER.debug('\t\tProcessing test: {0}'.format(test_name))

                            # Get the reference data we want to use as the override value
                            test_reference = self._get_test_reference_data(history, test_name)

                            # Finally, update the old override rule
                            self.update_test(build_variant_name, task_name, test_name, rule,
                                             test_reference)
                    except evergreen_client.Empty:
                        # _log_summary() will account for the case where we've skipped a task
                        # with no test results. (Hence no additional log message here.)
                        continue
        self._log_summary()

    def update_test(self, build_variant, task, test, rule, new_data, ticket=None):  # pylint: disable=too-many-arguments
        """Update the override reference data for the given test.

        :param str build_variant: The Evergreen name of the build variant
        :param str task: The Evergreen task
        :param str test: The Evergreen name of the test within that build variant
        :param str rule: The regression analysis rule (e.g. "reference", "ndays")
        :param dict new_data: The raw data for this test to use as a new reference point
        :param str ticket: The JIRA ticket to attach to this override reference point
        :return: The old value of the data for this particular build variant,
                test and rule, if one existed
        :rtype: dict
        """
        # Find the overrides for this build variant...
        if build_variant not in self.overrides:
            LOGGER.debug("Adding variant: {}".format(build_variant))
            self.overrides[build_variant] = {}
        if task not in self.overrides[build_variant]:
            LOGGER.debug("Adding task: {}".format(task))
            self.overrides[build_variant][task] = {'reference': {}, 'ndays': {}, 'threshold': {}}
        task_ovr = self.overrides[build_variant][task]

        # ...then, for this regression rule (e.g. 'reference', 'ndays')...
        if rule not in task_ovr:
            task_ovr[rule] = {}
        rule_ovr = task_ovr[rule]

        # ...and lastly, the raw data for the test
        try:
            previous_data = rule_ovr[test]
        except KeyError:
            previous_data = {}
        finally:
            rule_ovr[test] = new_data

        # attach a ticket number if one has been specified.
        rule_ovr[test]['ticket'] = []
        if 'ticket' in previous_data:
            curr_tickets = previous_data['ticket']
            if not isinstance(curr_tickets, list):
                curr_tickets = [curr_tickets]
            rule_ovr[test]['ticket'] = curr_tickets
        if ticket and ticket not in rule_ovr[test]['ticket']:
            rule_ovr[test]['ticket'].append(ticket)
        # ticket array is still empty
        elif not rule_ovr[test]['ticket']:
            raise UserWarning('Override rule for test {} under rule {} and build variant {} is '
                              'not associated with any tickets. Resulting file would be '
                              'considered invalid. Quitting'.format(test, rule, build_variant))
        return previous_data

    def get_tickets(self, rule='reference'):
        """ Return a list of all tickets mentioned in overrides

        :param str rule: Which rule to check for tickets. (Default reference)
        :return: A set of strings of the tickets referenced in the overrides
        """
        tickets = set()
        for variant_value in self.overrides.values():
            for task_value in variant_value.values():
                if rule in task_value:
                    ref = task_value[rule]
                    tickets = tickets.union(
                        set(
                            itertools.chain(*[
                                test['ticket'] for test in ref.values()
                                if 'ticket' in test.keys() and isinstance(test['ticket'], list)
                            ])))
        return tickets

    def rename_ticket(self, old_ticket, new_ticket):
        """Replace all occurrences of `old_ticket` in "ticket" fields with `new_ticket`."""

        for test in self.get_overrides_by_ticket(old_ticket):
            tickets = test[3]["ticket"]
            old_ticket_index = tickets.index(old_ticket)
            tickets.pop(old_ticket_index)
            tickets.insert(old_ticket_index, new_ticket)

    def get_overrides_by_ticket(self, ticket):
        """Get the overrides created by a given ticket.

        :param str ticket: The ID of a JIRA ticket (e.g. PERF-226)
        :rtype: A list of tuples of the form
                `(variant_name, type_name, test_name, override_object)`
        """

        overrides = []
        for variant_name, variant_overrides in self.overrides.items():
            for type_name, type_overrides in variant_overrides.items():
                for test_name, test_override in type_overrides.items():
                    if ticket in test_override["ticket"]:
                        overrides.append((variant_name, type_name, test_name, test_override))

        return overrides

    def _ticket_variant_rule_deletion(self, variant, task, rule, ticket, to_update, to_remove):  # pylint: disable=too-many-arguments
        """Given a ticket, build variant, task, and rule, figure out what can be completely removed
        and what tests will need to be updated.

        :type variant: str
        :type task: str
        :type rule: str
        :type ticket: str
        :param dict to_update: for every rule, record the build variants and corresponding list of
            tests that need to be updated, i.e. {rule -> {build variant -> { task -> [tests]}}}
        :param list[(str, str, str)] to_remove: record the build variant, rule, and test where the
            'ticket' key of a test was not a list. Presumably, this is a single ticket (str) and so
            we append it to a list to be removed as well. (Will not be needed when JSON validation
            of the override file is in place.)
        :rtype: (dict, list[(str, str, str)])
        """
        # Remove anything that can be blanket removed.

        new_tests = {}
        for (name, test) in self.overrides[variant][task][rule].items():
            if 'ticket' in test and test['ticket'].count(ticket) != len(test['ticket']):
                new_tests[name] = test
            else:
                self.delete_summary[variant][task] = [name]
        self.overrides[variant][task][rule] = new_tests

        for test in self.overrides[variant][task][rule]:
            # Look to see if it should be pulled from the ticket list
            check_tickets = self.overrides[variant][task][rule][test]['ticket']
            if ticket in check_tickets:
                if isinstance(check_tickets, list):
                    check_tickets.remove(ticket)
                    LOGGER.info('Deleting test {} from variant {}, task {} and rule {}, but '
                                'override remains'.format(test, variant, task, rule))
                    LOGGER.info('Remaining tickets are {}'.format(str(check_tickets)))
                    if rule is 'threshold':
                        LOGGER.info('Threshold override for {} from variant {} and task {} '
                                    'remains due to other outstanding '
                                    'tickets.'.format(test, variant, task))
                    else:
                        # Note: task to update is passed in separately, and may be a regex even
                        # There's no need to include it in this hierarchy
                        if rule not in to_update:
                            to_update[rule] = {}
                        if variant not in to_update[rule]:
                            to_update[rule][variant] = []
                        to_update[rule][variant].append(test)
                else:
                    to_remove.append((variant, task, rule, test))
        return (to_update, to_remove)

    def delete_overrides_by_ticket(self, ticket, rules, tasks='.*'):
        """Remove the overrides created by a given ticket.

        The override is completely removed if the ticket is the only
        one in the list. If there are other tickets in the list, the
        ticket is just removed from the list

        :param str ticket: The ID of a JIRA ticket (e.g. SERVER-20123)
        :param str rule: Which rule to delete from. (Default reference)
        :param str|list[str] tasks: Regex (or list of regex) matching tasks to update.
        """

        to_update = {}
        to_remove = []
        for build_variant in self.overrides.keys():
            self.delete_summary[build_variant] = {}
            for task in self.overrides[build_variant].keys():
                for rule in rules:
                    if rule in self.overrides[build_variant][task]:
                        (to_update, to_remove) = self._ticket_variant_rule_deletion(
                            build_variant, task, rule, ticket, to_update, to_remove)

                # Sometimes the above returns with a struct that just has empty leaves. If so
                # prune them.
                check_task = self.overrides[build_variant][task]
                if not check_task['ndays']\
                    and not check_task['reference']\
                    and not check_task['threshold']:
                    del self.overrides[build_variant][task]

            if not self.overrides[build_variant]:
                del self.overrides[build_variant]

        # Can be removed after merge with JSON validation precursor check.

        self._update_multiple_overrides(to_update, tasks)

    def save_to_file(self, file_or_filename):
        """Saves this override to a JSON file.

        :param file|str file_or_filename: A file or filename destination to save to
        """
        if isinstance(file_or_filename, str):
            with open(file_or_filename, 'w') as file_ptr:
                json.dump(
                    self.overrides,
                    file_ptr,
                    file_or_filename,
                    indent=4,
                    separators=[',', ':'],
                    sort_keys=True)
        elif isinstance(file_or_filename, file):
            json.dump(
                self.overrides, file_or_filename, indent=4, separators=[',', ':'], sort_keys=True)
        else:
            raise TypeError('Argument must be a file or filename')

    def validate(self, *args, **kwargs):
        """
        Validate this override configuration, raising an `AssertionError` if a problem is detected.
        """

        validate(self.overrides, *args, **kwargs)


def validate(overrides_dict, jira_api_auth=None):
    """
    Lint an override dictionary for valid structure/contents, throwing an `AssertionError` if a
    problem is detected. If you want to check whether ticket names contained in `overrides_dict`
    correspond to tickets that actually exist in the MongoDB JIRA server, set `jira_api_auth` to a
    `("jira_username", "jira_password")` tuple. Otherwise, ticket names will only undergo a rough
    regex validation.
    """

    assert len(overrides_dict) > 0, "No variants specified."
    expected_keys_per_type = {
        "ndays": ["results", "threads", "ticket", "revision", "create_time"],
        "reference": ["results", "threads", "ticket", "revision"],
        "threshold": ["threshold", "thread_threshold", "ticket"]
    }

    # We need to query the JIRA API to determine whether a particular ticket exists. In the interest
    # of decreasing running time, instead of making an API call per ticket name while iterating
    # through `overrides_dict` (which we would obviously memoize since there aren't many /unique/
    # ticket names in any given override file, though that would still result in at least a few
    # different HTTP requests), we store all of the ticket names as they're encountered and perform
    # one bulk lookup at the end of the validation.
    all_tickets = set()

    query_jira_for_tickets = jira_api_auth is not None

    for variant_name, variant_override in overrides_dict.items():
        assert len(variant_override) > 0, "No tasks specified in variant {}.".format(variant_name)
        for task_name, task_override in variant_override.items():
            for override_type in ["reference", "ndays", "threshold"]:
                assert override_type in task_override, \
                    'Required override type "{}" missing from override["{}"]["{}"]'.format(
                        override_type, variant_name, task_name)

                required_keys = expected_keys_per_type[override_type]
                for test_name, test_override in task_override[override_type].items():
                    for key in required_keys:
                        assert key in test_override, \
                            ('Required key "{}" not present in override["{}"]["{}"]["{}"]'
                             '["{}"]').format(
                                 key, variant_name, task_name, override_type, test_name)

                    if override_type in ["reference", "ndays"]:
                        _validate_results_dict(variant_name, task_name, override_type, test_name,
                                               test_override["results"])

                    ticket_list = test_override["ticket"]
                    _validate_ticket_list(variant_name, task_name, override_type, test_name,
                                          ticket_list)

                    if query_jira_for_tickets:
                        all_tickets.update(ticket_list)

    if query_jira_for_tickets and all_tickets:
        _check_tickets_exist(all_tickets, jira_api_auth)


def _validate_results_dict(variant_name, task_name, override_type, test_name, result_dict):
    """
    Validate `result_dict`, a "results" dictionary from an override configuration, throwing an
    `AssertionError` if a problem is detected.
    """

    thread_specific_override = False
    for num_threads, thread_override in result_dict.items():
        try:
            num_threads = int(num_threads)
        except ValueError:
            continue

        thread_specific_override = True
        assert "ops_per_sec" in thread_override, \
            ('"ops_per_sec" key missing in override["{}"]["{}"]["{}"]'
             '["{}"]["{}"].').format(variant_name, task_name, override_type, test_name, num_threads)

    assert thread_specific_override, \
        ('No override data found in override["{}"]["{}"]["{}"]'
         '["{}"]["results"]').format(variant_name, task_name, override_type, test_name)


def _validate_ticket_list(variant_name, task_name, override_type, test_name, ticket_list):
    """
    Validate `ticket_list`, a list of tickets from an override configuration, throwing an
    `AssertionError` if a problem is detected.
    """

    ticket_name_regex = r"^(PERF|SERVER|BF)-\d+$"
    err_msg_ticket_path = 'override["{}"]["{}"]["{}"]["{}"]["ticket"]'.format(
        variant_name, task_name, override_type, test_name)
    assert isinstance(ticket_list, list), err_msg_ticket_path + " is not a list."
    assert ticket_list, err_msg_ticket_path + " is empty."

    for ticket_name in ticket_list:
        assert isinstance(ticket_name, basestring), \
            "Ticket `{}` in {} is not a string.".format(
                ticket_name, err_msg_ticket_path)

        valid_ticket_name = re.match(ticket_name_regex, ticket_name) is not None
        assert valid_ticket_name, \
            ('Ticket name "{}" in {} is invalid; it must satisfy the following ' \
            'regex: "{}"').format(ticket_name, err_msg_ticket_path, ticket_name_regex)


def _check_tickets_exist(ticket_names, jira_api_auth):
    """
    Check whether all ticket names in `ticket_names` exist on the  `https://jira.mongodb.org` JIRA
    server by querying the API. If any tickets are found to not exist an `AssertionError` with a
    helpful message will be raised.
    """

    jira_api_url = "https://jira.mongodb.org/rest/api/2/search"
    ticket_jql_query = {"jql": "issueKey in ({})".format(",".join(ticket_names))}
    api_resp = requests.post(jira_api_url, json=ticket_jql_query, auth=jira_api_auth)

    assert api_resp.status_code in [200, 400], \
        'Unexpected HTTP response from JIRA API for "{}":\n{}'.format(jira_api_url, vars(api_resp))
    assert api_resp.status_code == 200, "\n".join(api_resp.json()["errorMessages"])
