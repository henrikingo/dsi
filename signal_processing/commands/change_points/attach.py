"""
Functionality to attach / detach test identifiers from build failures.
"""

from __future__ import print_function

from collections import defaultdict

import click
import structlog

from signal_processing.commands import helpers as helpers

from signal_processing.etl_jira_mongo import FIELDS, lookup
from signal_processing.keyring.jira_keyring import jira_keyring

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


@click.command(name='attach')
@click.pass_obj
@click.option(
    '--exclude',
    'excludes',
    multiple=True,
    help='''Exclude all points matching this pattern. This parameter can be provided
multiple times.''')
@click.option(
    '--username',
    'username',
    required=False,
    help='''The jira username, you will be prompted if none is available here or
in the keyring. If credentials are provided and the command succeeds and a keyring is in use,
the credentials are stored in the keyring for subsequent calls.''')
@click.option(
    '--password',
    'password',
    required=False,
    help='''The jira password, you will be prompted if none is available here or
in the keyring. If credentials are provided and the command succeeds and a keyring is in use,
the credentials are stored in the keyring for subsequent calls.''')
@click.option(
    '--keyring / --no-keyring',
    'use_keyring',
    is_flag=True,
    default=True,
    help='Never use keyring if --no-keyring is provided.')
@click.option(
    '--guest',
    'use_keyring',
    flag_value=False,
    default=True,
    help='Never use keyring same as --no-keyring.')
@click.option(
    '--fail / --fix',
    'fail',
    is_flag=True,
    default=True,
    help='Set the first fail or fix. Default is first fail.')
@click.argument('build_failure', required=True)
@click.argument('revision', required=True)
@click.argument('project', required=True)
@click.argument('variant', required=False)
@click.argument('task', required=False)
@click.argument('test', required=False)
def attach_command(command_config, excludes, username, password, use_keyring, fail, build_failure,
                   revision, project, variant, task, test):
    # pylint: disable=too-many-arguments, too-many-locals
    """
    Attach meta data to a build failure. This command looks for points matching the project /
    variant / task / test when attempting to detach.


Argument can be strings.

\b
BUILD FAILURE, the Jira issue id, something like BF-0001.
REVISION, the revision id.
PROJECT, the project name e.g. sys-perf.
VARIANT, the build variant e.g. linux-standalone or '/repl/'.
VARIANT, the task e.g. bestbuy_agg or '/bestbuy/'.
Test, the test e.g. canary_client-cpuloop-10x or '/canary/'.
\b
Examples:
\b
    # Attach a specific first_fail_revision point
    $> change-points attach BF-0001 e573d7f2f908f3fbe96716851cd1b1e3d65fe7c9 sys-perf \
    linux-shard-lite mongos_workloads mongos_insert_vector_sharded_raw
OR:
    $> change-points attach BF-0001 e573d7f2f908f3fbe96716851cd1b1e3d65fe7c9 sys-perf \
    linux-shard-lite mongos_workloads mongos_insert_vector_sharded_raw --fail

\b
    # Attach a specific fix_revision point
    $> change-points attach BF-0001 e573d7f2f908f3fbe96716851cd1b1e3d65fe7c9 sys-perf \
    linux-shard-lite mongos_workloads mongos_insert_vector_sharded_raw --fix

\b
    # Attach all tests for the specific change point task
    $> change-points attach BF-0001 e573d7f2f908f3fbe96716851cd1b1e3d65fe7c9 sys-perf \
    linux-shard-lite mongos_workloads

\b
    # Attach all tasks / tests for the specific change point variant
    $> change-points attach BF-0001 e573d7f2f908f3fbe96716851cd1b1e3d65fe7c9 sys-perf \
    linux-shard-lite

\b
    # Attach all variants / tasks / tests for the specific change point project
    $> change-points attach BF-0001 e573d7f2f908f3fbe96716851cd1b1e3d65fe7c9 sys-perf

\b
    # You are a guest on this host and don't want your credentials saved.
    $> change-points attach BF-11372  e573d7f2f908f3fbe96716851cd1b1e3d65fe7c9 sys-perf\
     --no-keyring --username jira_user

    # same as --no-keyring
    $> change-points attach BF-11372  e573d7f2f908f3fbe96716851cd1b1e3d65fe7c9 sys-perf\
     --guest --username jira_user

"""
    with jira_keyring(username, password, use_keyring=use_keyring) as jira:
        issue = jira.issue(build_failure)

        points = command_config.points
        query = helpers.process_params_for_points(project, variant, task, test, revision=revision)
        LOG.debug('processed params', query=query)

        matching_tasks = helpers.filter_legacy_tasks(helpers.get_matching_tasks(points, query))
        LOG.debug('matched tasks', matching_tasks=matching_tasks)

        exclude_patterns = helpers.process_excludes(excludes)
        test_identifiers = [
            test_identifier for test_identifier in helpers.generate_tests(matching_tasks)
            if not helpers.filter_tests(test_identifier['test'], exclude_patterns)
        ]
        LOG.debug('matched test_identifiers', test_identifiers=test_identifiers)

        attach(issue, test_identifiers, not fail, command_config)


@click.command(name='detach')
@click.pass_obj
@click.option(
    '--exclude',
    'excludes',
    multiple=True,
    help='''Exclude all points matching this pattern. This parameter can be provided
multiple times.''')
@click.option(
    '--username',
    'username',
    required=False,
    help='''The jira username, you will be prompted if none is available here or
in the keyring. If credentials are provided and the command succeeds and a keyring is in use,
the credentials are stored in the keyring for subsequent calls.''')
@click.option(
    '--password',
    'password',
    required=False,
    help='''The jira password, you will be prompted if none is available here or
in the keyring. If credentials are provided and the command succeeds and a keyring is in use,
the credentials are stored in the keyring for subsequent calls.''')
@click.option(
    '--keyring / --no-keyring',
    'use_keyring',
    is_flag=True,
    default=True,
    help='Never use keyring if --no-keyring is provided.')
@click.option(
    '--guest',
    'use_keyring',
    flag_value=False,
    default=True,
    help='Never use keyring same as --no-keyring.')
@click.option(
    '--fail / --fix',
    'fail',
    is_flag=True,
    default=True,
    help='Set the first fail or fix. Default is first fail.')
@click.argument('build_failure', required=True)
@click.argument('revision', required=True)
@click.argument('project', required=True)
@click.argument('variant', required=False)
@click.argument('task', required=False)
@click.argument('test', required=False)
def detach_command(command_config, excludes, username, password, use_keyring, fail, build_failure,
                   revision, project, variant, task, test):
    # pylint: disable=too-many-arguments, too-many-locals
    """
    Detach meta data from a build failure. This command looks for points matching the project /
    variant / task / test when attempting to detach.

Argument can be strings.

\b
BUILD FAILURE, the Jira issue id, something like BF-0001.
REVISION, the revision id.
PROJECT, the project name e.g. sys-perf.
VARIANT, the build variant e.g. linux-standalone or '/repl/'.
VARIANT, the task e.g. bestbuy_agg or '/bestbuy/'.
Test, the test e.g. canary_client-cpuloop-10x or '/canary/'.
\b
Examples:
\b
    # Detach a specific first_fail_revision point
    $> change-points detach BF-0001 e573d7f2f908f3fbe96716851cd1b1e3d65fe7c9 sys-perf \
    linux-shard-lite mongos_workloads mongos_insert_vector_sharded_raw
OR:
    $> change-points detach BF-0001 e573d7f2f908f3fbe96716851cd1b1e3d65fe7c9 sys-perf \
    linux-shard-lite mongos_workloads mongos_insert_vector_sharded_raw --fail

    # Detach a specific fix_revision  point
    $> change-points detach BF-0001 e573d7f2f908f3fbe96716851cd1b1e3d65fe7c9 sys-perf \
    linux-shard-lite mongos_workloads mongos_insert_vector_sharded_raw --fix

\b
    # Detach all tests for the specific point task
    $> change-points detach BF-0001 e573d7f2f908f3fbe96716851cd1b1e3d65fe7c9 sys-perf \
    linux-shard-lite mongos_workloads

\b
    # Detach all tasks / tests for the specific point variant
    $> change-points detach BF-0001 e573d7f2f908f3fbe96716851cd1b1e3d65fe7c9 sys-perf \
    linux-shard-lite

\b
    # Detach all variants / tasks / tests for the specific point project
    $> change-points detach BF-0001 e573d7f2f908f3fbe96716851cd1b1e3d65fe7c9 sys-perf

\b
    # You are a guest on this host and don't want your credentials saved.
    $> change-points detach BF-11372  e573d7f2f908f3fbe96716851cd1b1e3d65fe7c9 sys-perf\
     --no-keyring --username jira_user

    # same as --no-keyring
    $> change-points detach BF-11372  e573d7f2f908f3fbe96716851cd1b1e3d65fe7c9 sys-perf\
     --guest --username jira_user
"""

    with jira_keyring(username, password, use_keyring=use_keyring) as jira:
        issue = jira.issue(build_failure)

        query = helpers.process_params_for_points(project, variant, task, test, revision=revision)
        LOG.debug('processed params', query=query)

        matching_tasks = helpers.filter_legacy_tasks(
            helpers.get_matching_tasks(command_config.points, query))
        LOG.debug('matched tasks', matching_tasks=matching_tasks)

        exclude_patterns = helpers.process_excludes(excludes)
        test_identifiers = [
            test_identifier for test_identifier in helpers.generate_tests(matching_tasks)
            if not helpers.filter_tests(test_identifier['test'], exclude_patterns)
        ]
        LOG.debug('matched test_identifiers', test_identifiers=test_identifiers)
        detach(issue, test_identifiers, not fail, command_config)
