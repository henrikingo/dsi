"""
Functionality to list build failures and their linked change points.
"""
from __future__ import print_function

import structlog

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
