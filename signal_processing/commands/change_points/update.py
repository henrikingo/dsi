"""
Functionality to mark change points.
"""
import logging

import click

from signal_processing.commands import helpers as helpers
from signal_processing.commands.helpers import stringify_json, filter_excludes

LOG = logging.getLogger(__name__)


def update_change_points(processed_type, query, exclude_patterns, command_config):
    """
    update an existing processed change point.

    :param str processed_type: 'hidden' for hidden otherwise 'real'.
    :param dict query: Find change points matching this query.
    :param list(re) exclude_patterns: Filter any points matching this list of excludes.
    :param CommandConfig command_config: Common configuration.
    """
    LOG.debug('update "%s"', processed_type)
    collection = command_config.processed_change_points

    for point in filter_excludes(collection.find(query), query.keys(), exclude_patterns):
        LOG.info("update before: %s", stringify_json(point, compact=command_config.compact))
        point['processed_type'] = processed_type
        if not command_config.dry_run:
            update = {'$set': {'processed_type': processed_type}}
            res = collection.update_one({'_id': point['_id']}, update)
            LOG.debug('update: result "%r"', res.raw_result)


@click.command(name='update')
@click.pass_obj
@click.option(
    '--exclude',
    'exclude_patterns',
    multiple=True,
    help='Exclude all points matching this pattern. This parameter can be provided ' +
    'multiple times.')
@click.option(
    '--processed-type',
    'processed_type',
    type=click.Choice(helpers.PROCESSED_TYPES),
    default=helpers.PROCESSED_TYPE_HIDDEN,
    required=True,
    help='The value to set processed_type.')
@click.argument('revision', required=True)
@click.argument('project', required=True)
@click.argument('variant', required=False)
@click.argument('task', required=False)
@click.argument('test', required=False)
@click.argument('thread_level', required=False)
def update_command(command_config, exclude_patterns, processed_type, revision, project, variant,
                   task, test, thread_level):
    # pylint: disable=too-many-arguments, too-many-function-args
    """
    Update an existing processed change point(s).
Arguments can be string or patterns, A pattern starts with /.

\b
REVISION, the revision of the change point. This parameter is mandatory.
PROJECT, the project name or a regex (like /^sys-perf-3.*/ or /^(sys-perf|performance)$/). This
parameter is mandatory.
VARIANT, the build variant or a regex.
TASK, the task name or a regex.
TEST, the test name or a regex.
THREADS, the thread level or a regex.
\b
You can use '' in place of VARIANT, TASK, TEST, THREADS if you want to match all. See the
examples.
\b
Examples:
    $> revision=bad5afd612e8fc917fb035d8333cffd7d68a37cc
\b
    # dry run on all sys-perf points
    $> change-points update $revision sys-perf -n
\b
    # update all *existing* sys-perf change points for a specific sys perf revision as hidden
    $> change-points update $revision sys-perf
\b
    # update some existing processed change point as acknowledged
    $> change-points update $revision sys-perf linux-1-node-replSet --processed-type acknowledged
    $> change-points update $revision sys-perf '/linux-.-node-replSet/' \\
    --processed-type acknowledged
    $> change-points update $revision sys-perf revision linux-1-node-replSet \\
    change_streams_latency --exclude '/^(fio_|canary_)/' --processed-type acknowledged
    $> change-points update $revision sys-perf linux-1-node-replSet change_streams_latency \\
       '/^(fio_|canary_)/' --processed-type acknowledged
\b
    #  hide all the revision sys-perf find_limit-useAgg 8 thread level
    $> change-points update  $revision sys-perf '' '' find_limit-useAgg 8 --processed-type hidden
    $> change-points update  $revision sys-perf '' '' find_limit-useAgg 8
\b
    #  update all the revision sys-perf find_limit-useAgg 8 thread level as acknowledged
    $> change-points update  $revision sys-perf '' '' find_limit-useAgg 8 \\
    --processed-type acknowledged
\b
    #  hide all the revision sys-perf find_limit-useAgg all thread level
    $> change-points update $revision sys-perf '' '' find_limit-useAgg --processed-type hidden
    $> change-points update $revision sys-perf '' '' find_limit-useAgg
\b
    #  update all the revision sys-perf find_limit-useAgg all thread level as acknowledgedreal
    $> change-points update $revision sys-perf '' '' find_limit-useAgg '' \\
    --processed-type acknowledged
"""
    query = helpers.process_params(
        project, variant, task, test, revision=revision, thread_level=thread_level)
    update_change_points(processed_type, query, helpers.process_excludes(exclude_patterns),
                         command_config)
