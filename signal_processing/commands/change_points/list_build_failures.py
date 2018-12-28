"""
Functionality to list build failures and their linked change points.
"""

from __future__ import print_function

import click
import structlog

from signal_processing.commands import helpers as helpers

from signal_processing.commands.helpers import stringify_json

LOG = structlog.getLogger(__name__)


def list_build_failures(query, human_readable, command_config):
    """
    Print a list of build failures with linked change points.

    :param dict query: Find linked build failures matching this query.
    :param bool human_readable: Print in a more human-friendly format.
    :param CommandConfig command_config: Common configuration.
    """
    LOG.debug('Print build failures')
    collection = command_config.database.linked_build_failures

    # TODO: Get rid of the following four lines once field names are consistent across collections
    # (PERF-1590).
    if 'variant' in query:
        query['buildvariants'] = query.pop('variant')
    if 'task' in query:
        query['tasks'] = query.pop('task')

    if 'suspect_revision' in query:
        suspect_revision = query.pop('suspect_revision')
        if suspect_revision:
            query['revision'] = suspect_revision

    for build_failure in collection.find(query):
        if human_readable:
            _print_human_readable(build_failure)
        else:
            print(stringify_json(build_failure, command_config.compact))


def _print_human_readable(build_failure):
    """
    Print a information of  a build failure and its linked change points in a human-friendly format.
    This formatting will omit non-essential fields. Each BF will have the following format:

            BF-XXXX
            Summary: <BF summary>
            Revision: <revision>
            Project(s): [<project1>, <project2>, ...]
            Variant(s): [<variant1>, <variant2>, ...]
            Task(s): [<task1>, <task2>, ...]
                Change points:
                <project>/<variant>/<task>/<thread_level>
                    All suspect revisions:
                    <revision1>
                    <revision2>
                    ...

    :param dict build_failure: Dictionary representing a document from the `linked_build_failures`
    view.
    """
    print(build_failure['_id'])
    print('Summary: {:80.80}'.format(build_failure.get('summary', '')))
    print('Match Revision: {}'.format(build_failure['revision']))
    print('First Failing Revision: {}'.format(build_failure['first_failing_revision']))
    print('Fix Revision: {}'.format(build_failure['fix_revision']))
    print('Project(s): {}'.format(build_failure['project']))
    print('Variant(s): {}'.format(build_failure.get('buildvariants', [])))
    print('Task(s): {}'.format(build_failure.get('tasks', [])))
    print('Change points:')
    for change_point in build_failure['linked_change_points']:
        print('\t{}/{}/{}/{}/{}'.format(change_point['project'], change_point['variant'],
                                        change_point['task'], change_point['test'],
                                        change_point['thread_level']))
        print('\tAll Suspect Revisions:')
        for revision in change_point['all_suspect_revisions']:
            print('\t\t{}'.format(revision))


@click.command(name='list-build-failures')
@click.pass_obj
@click.option(
    '--human-readable',
    'human_readable',
    is_flag=True,
    help='Print output in a more human-friendly output.')
@click.argument('revision', required=True)
@click.argument('project', required=True)
@click.argument('variant', required=False)
@click.argument('task', required=False)
@click.argument('test', required=False)
def list_build_failures_command(command_config, human_readable, revision, project, variant, task,
                                test):
    # pylint: disable=too-many-arguments, too-many-function-args
    """
    Print list of build failures and their linked change points.

Arguments can be string or patterns, A pattern starts with /.

\b
REVISION, the revision of the change point.
PROJECT, the project name or a regex (like /^sys-perf-3.*/ or /^(sys-perf|performance)$/).
VARIANT, the build variant or a regex.
TASK, the task name or a regex.
TEST, the test name or a regex.
\b
You can use '' in place of VARIANT, TASK, TEST, if you want to match all. See the examples.
\b
Examples:
    $> revision=a1b225bcf0e9791b14649df385b3f3f9710a98ab
\b
    # List all build failures
    $> change-points list-build-failures
\b
    # List all build failures for a revision
    $> change-points list-build-failures $revision
\b
    # List sys-perf build failures for a revision
    $> change-points list-build-failures $revision sys-perf
\b
    # List sys-perf build failures (any revision)
    $> change-points list-build-failures '' sys-perf
\b
    # List build failures matching criteria
    $> change-points list-build-failures $revision sys-perf linux-1-node-replSet
    $> change-points list-build-failures $revision sys-perf '/linux-.-node-replSet/'
\b
    # List all build failures with sys-perf find_limit-useAgg (any revision)
    $> change-points list-build-failures '' sys-perf '' '' find_limit-useAgg
\b
    # List build failures in a more human-friendly format
    $> change-points list-build-failures --human-readable
    $> change-points list-build-failures $revision sys-perf linux-1-node-replSet --human-readable
"""
    query = helpers.process_params(project, variant, task, test, revision=revision)
    list_build_failures(query, human_readable, command_config)
