"""
Commands to attach / detach test identifiers from build failures.
"""
import click
import structlog

from signal_processing.change_points import attach
from signal_processing.commands import helpers

from signal_processing.keyring.jira_keyring import jira_keyring

LOG = structlog.getLogger(__name__)


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
@click.argument('variant', required=True)
@click.argument('task', required=True)
@click.argument('test', required=True)
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

        attach.attach(issue, test_identifiers, not fail, command_config)


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
        attach.detach(issue, test_identifiers, not fail, command_config)
