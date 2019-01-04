"""
Functionality to attach / detach test identifiers from build failures.
"""
from collections import defaultdict

import structlog

from signal_processing.etl_jira_mongo import lookup, FIELDS

LOG = structlog.getLogger(__name__)

REMOTE_KEYS = [
    'first_failing_revision', 'fix_revision', 'project', 'buildvariants', 'tasks', 'tests'
]


def get_field_value(build_failure, field_name):
    """
    Get the value of a field name as a set from build failure.

    :param jira.Issue build_failure: The jira issue.
    :param str field_name: The jira field name.
    :return: A set of values.
    """
    value = lookup(build_failure, FIELDS[field_name])
    if value is None:
        value = set()
    else:
        value = set(value)
    return value


def get_issue_state(build_failure):
    """
    Get the remote state of the JIRA issue for the relevant fields. These fields are:
        * first_failing_revision
        * fix_revision
        * project
        * buildvariants
        * tasks
        * tests

    :param jira.Issue build_failure: A reference to the remote build failure.

    :return: A dict of sets containing the remote data from JIRA.
    :rtype: dict(str,set()).
    """
    return {key: get_field_value(build_failure, key) for key in REMOTE_KEYS}


def map_identifiers(test_identifiers, fix, revision_field_name='suspect_revision'):
    """
    Map test identifiers to a dict of sets. This dict ensures that the test_identifiers use
    consistent field names.

    :param list(dict) test_identifiers: A list of test identifiers.
    :param bool fix: If True then the test_identifiers are for fix_revision otherwise, it is for
    first_failing_revision.
    :param str revision_field_name: The field name for a revision. It is suspect_revision for
    change points and revision for points.
    :return: A dict of sets for the test_identifiers.
    :rtype: dict(str, set()).
    """
    update = defaultdict(set)
    mapping = {'project': 'project', 'buildvariants': 'variant', 'tasks': 'task', 'tests': 'test'}

    if fix:
        mapping['fix_revision'] = revision_field_name
    else:
        mapping['first_failing_revision'] = revision_field_name

    for key, mapped_key in mapping.iteritems():
        update[key] = update[key].union(
            [test_identifier[mapped_key] for test_identifier in test_identifiers])

    return dict(**update)


def attach(build_failure, test_identifiers, fix, command_config):
    """
    Attach the meta data to a build failure.

    :param jira.Issue build_failure: The Build Failure issue.
    :param list(dict) test_identifiers: The change point meta data.
    :param bool fix: Is this the first failing or fix revision.
    :param CommandConfig command_config: Common configuration.
    """
    LOG.debug(
        'attach',
        build_failure=build_failure,
        test_identifiers=test_identifiers,
        command_config=command_config)

    if test_identifiers:
        original = get_issue_state(build_failure)
        LOG.debug('attach', original=original)

        update = map_identifiers(test_identifiers, fix, revision_field_name='revision')
        LOG.debug('attach', update=update)

        field_updates = {}
        for key in update:
            field_name = FIELDS[key][-1]
            delta = update[key].difference(original[key])
            if delta:
                field_updates[field_name] = list(original[key].union(update[key]))

        LOG.debug('attach', build_failure=build_failure, field_updates=field_updates)
        if not command_config.dry_run and field_updates:
            build_failure.update(fields=field_updates)


def detach(build_failure, test_identifiers, fix, command_config):
    """
    Detach the meta data to a build failure.

    :param jira.Issue build_failure: The Build Failure issue.
    :param list(dict) test_identifiers: The change point meta data.
    :param bool fix: Is this the first failing or fix revision.
    :param CommandConfig command_config: Common configuration.
    """
    LOG.debug(
        'detach',
        build_failure=build_failure,
        test_identifiers=test_identifiers,
        command_config=command_config)

    if test_identifiers:
        original = get_issue_state(build_failure)
        LOG.debug('detach', original=original)

        update = map_identifiers(test_identifiers, fix, revision_field_name='revision')
        LOG.debug('detach', update=update)

        field_updates = {}
        for key in update:
            field_name = FIELDS[key][-1]
            delta = original[key].intersection(update[key])
            if delta:
                field_updates[field_name] = list(original[key].difference(update[key]))

        LOG.debug('detach', build_failure=build_failure, field_updates=field_updates)

        if not command_config.dry_run and field_updates:
            build_failure.update(fields=field_updates)
